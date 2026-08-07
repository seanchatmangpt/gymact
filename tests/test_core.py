from __future__ import annotations

import json

import anyio
import pytest
from fastapi.testclient import TestClient
from fastmcp import FastMCP
from fastmcp.client import Client
from faststream import FastStream
from typer.testing import CliRunner

from gymact import (
    ActuationIntent,
    AllowListAuthorityResolver,
    GymAct,
    MemoryProvider,
    ProfileAuthority,
    Standing,
)
from gymact.cli import app as cli_app
from gymact.surfaces.fastapi import create_app
from gymact.surfaces.fastmcp import create_mcp
from gymact.surfaces.faststream import bind_stream_handlers, create_stream_app

AUTHORITY = "urn:test:authority"


def authorized_runtime() -> GymAct:
    return GymAct(authority_resolver=AllowListAuthorityResolver({AUTHORITY}))


def test_semantic_profile_is_public_ontology_only(tmp_path) -> None:
    authority = ProfileAuthority()
    result = authority.validate()
    assert result.conforms, result.report_text
    assert result.custom_tbox_terms == ()
    assert result.triple_count >= 40
    exported = authority.export(tmp_path)
    assert set(exported) == {"profile.ttl", "profile.shacl.ttl"}
    assert all(path.exists() and path.stat().st_size > 0 for path in exported.values())


@pytest.mark.asyncio
async def test_authority_refusal_does_not_change_world() -> None:
    runtime = GymAct()
    runtime.register_provider(MemoryProvider(requires_authority=True))
    episode = await runtime.create_episode("memory", config={"initial": {"safe": False}})
    result = await runtime.act(
        ActuationIntent(
            episode_id=episode.episode_id,
            affordance="set",
            payload={"key": "safe", "value": True},
            idempotency_key="refused-once",
        )
    )
    assert result.accepted is False
    assert result.standing == Standing.REFUSED
    assert result.receipt.reason == "LIVE_AUTHORITY_REQUIRED"
    observation = await runtime.observe(episode.episode_id)
    assert observation.state == {"safe": False}
    assert result.receipt.pre_state_digest == result.receipt.post_state_digest


@pytest.mark.asyncio
async def test_reference_string_without_admission_is_not_authority() -> None:
    runtime = GymAct()
    runtime.register_provider(MemoryProvider(requires_authority=True))
    episode = await runtime.create_episode("memory", config={"initial": {"safe": False}})
    result = await runtime.act(
        ActuationIntent(
            episode_id=episode.episode_id,
            affordance="set",
            payload={"key": "safe", "value": True},
            authority_ref=AUTHORITY,
            idempotency_key="unresolved-authority",
        )
    )
    assert result.standing == Standing.REFUSED
    assert result.receipt.reason == "AUTHORITY_NOT_ADMITTED"
    assert (await runtime.observe(episode.episode_id)).state == {"safe": False}


@pytest.mark.asyncio
async def test_authorized_actuation_is_idempotent_and_independently_verified() -> None:
    runtime = authorized_runtime()
    runtime.register_provider(MemoryProvider(requires_authority=True))
    episode = await runtime.create_episode("memory", config={"initial": {"count": 0}})
    intent = ActuationIntent(
        episode_id=episode.episode_id,
        affordance="increment",
        payload={"key": "count", "amount": 1},
        authority_ref=AUTHORITY,
        idempotency_key="increment-once",
    )
    first = await runtime.act(intent)
    second = await runtime.act(intent)
    assert first == second
    assert first.receipt.authority_evidence_ref is not None
    observation = await runtime.observe(episode.episode_id)
    assert observation.state["count"] == 1
    verification = await runtime.verify(episode.episode_id, {"count": 1})
    assert verification.passed is True
    assert first.receipt.verification_id is None


@pytest.mark.asyncio
async def test_concurrent_same_intent_actuates_once() -> None:
    runtime = authorized_runtime()
    runtime.register_provider(MemoryProvider(requires_authority=True))
    episode = await runtime.create_episode("memory", config={"initial": {"count": 0}})
    intent = ActuationIntent(
        episode_id=episode.episode_id,
        affordance="increment",
        payload={"key": "count", "amount": 1},
        authority_ref=AUTHORITY,
        idempotency_key="concurrent-increment",
    )
    results = []

    async def invoke() -> None:
        results.append(await runtime.act(intent))

    async with anyio.create_task_group() as group:
        group.start_soon(invoke)
        group.start_soon(invoke)

    assert len(results) == 2
    assert results[0] == results[1]
    assert (await runtime.observe(episode.episode_id)).state == {"count": 1}


@pytest.mark.asyncio
async def test_idempotency_key_conflict_is_refused_without_second_actuation() -> None:
    runtime = GymAct()
    runtime.register_provider(MemoryProvider())
    episode = await runtime.create_episode("memory", config={"initial": {"value": 0}})
    first = ActuationIntent(
        episode_id=episode.episode_id,
        affordance="set",
        payload={"key": "value", "value": 1},
        idempotency_key="same-key",
    )
    conflicting = first.model_copy(update={"payload": {"key": "value", "value": 2}})
    assert (await runtime.act(first)).accepted is True
    refused = await runtime.act(conflicting)
    assert refused.standing == Standing.REFUSED
    assert refused.receipt.reason == "IDEMPOTENCY_KEY_CONFLICT"
    assert (await runtime.observe(episode.episode_id)).state == {"value": 1}


@pytest.mark.asyncio
async def test_provider_error_is_receipted_and_does_not_claim_success() -> None:
    runtime = GymAct()
    runtime.register_provider(MemoryProvider())
    episode = await runtime.create_episode("memory", config={"initial": {"value": 1}})
    result = await runtime.act(
        ActuationIntent(
            episode_id=episode.episode_id,
            affordance="does-not-exist",
            idempotency_key="bad-affordance",
        )
    )
    assert result.accepted is False
    assert result.standing == Standing.BLOCKED
    assert result.receipt.reason is not None
    assert result.receipt.reason.startswith("PROVIDER_ERROR:ValueError:")
    assert result.receipt.pre_state_digest == result.receipt.post_state_digest


@pytest.mark.asyncio
async def test_memory_provider_delete_increment_verify_and_teardown() -> None:
    runtime = GymAct()
    runtime.register_provider(MemoryProvider())
    episode = await runtime.create_episode("memory", config={"initial": {"x": 1, "drop": 2}})
    delete = await runtime.act(
        ActuationIntent(
            episode_id=episode.episode_id,
            affordance="delete",
            payload={"key": "drop"},
            idempotency_key="delete",
        )
    )
    assert delete.accepted
    increment = await runtime.act(
        ActuationIntent(
            episode_id=episode.episode_id,
            affordance="increment",
            payload={"key": "x", "amount": 3},
            idempotency_key="increment",
        )
    )
    assert increment.observation is not None
    assert increment.observation.state == {"x": 4}
    assert (await runtime.verify(episode.episode_id, {"x": 99})).passed is False
    receipt = await runtime.teardown(episode.episode_id)
    assert receipt.standing == Standing.ALIVE
    with pytest.raises(KeyError, match="unknown episode"):
        await runtime.observe(episode.episode_id)


@pytest.mark.asyncio
async def test_checkpoint_restore_requires_admitted_authority() -> None:
    runtime = authorized_runtime()
    runtime.register_provider(MemoryProvider(requires_authority=True))
    episode = await runtime.create_episode("memory", config={"initial": {"value": 1}})
    checkpoint = await runtime.checkpoint(episode.episode_id)
    await runtime.act(
        ActuationIntent(
            episode_id=episode.episode_id,
            affordance="set",
            payload={"key": "value", "value": 2},
            authority_ref=AUTHORITY,
        )
    )
    refused = await runtime.restore(episode.episode_id, checkpoint)
    assert refused.standing == Standing.REFUSED
    restored = await runtime.restore(episode.episode_id, checkpoint, authority_ref=AUTHORITY)
    assert restored.standing == Standing.ALIVE
    assert restored.authority_evidence_ref is not None
    assert (await runtime.observe(episode.episode_id)).state == {"value": 1}


def test_fastapi_surface_executes_real_episode_and_contract_routes() -> None:
    runtime = GymAct()
    runtime.register_provider(MemoryProvider())
    client = TestClient(create_app(runtime))
    assert client.get("/health").json()["status"] == "ALIVE"
    assert client.get("/profile").json()["conforms"] is True
    assert client.get("/providers").json() == {"providers": ["memory"]}
    response = client.post(
        "/episodes", json={"provider": "memory", "config": {"initial": {"x": 1}}}
    )
    assert response.status_code == 200
    episode_id = response.json()["episode_id"]
    assert client.get(f"/episodes/{episode_id}/observations/latest").json()["state"] == {"x": 1}
    checkpoint = client.get(f"/episodes/{episode_id}/checkpoint").json()["checkpoint"]
    action = client.post(
        f"/episodes/{episode_id}/actions",
        json={
            "episode_id": episode_id,
            "affordance": "set",
            "payload": {"key": "x", "value": 2},
            "idempotency_key": "api-set",
            "operation": "act",
        },
    )
    assert action.status_code == 200
    assert action.json()["accepted"] is True
    mismatch = client.post(
        f"/episodes/{episode_id}/actions",
        json={"episode_id": "wrong", "affordance": "set", "payload": {}},
    )
    assert mismatch.status_code == 409
    verification = client.post(f"/episodes/{episode_id}/verify", json={"expected": {"x": 2}})
    assert verification.json()["passed"] is True
    restored = client.post(
        f"/episodes/{episode_id}/restore", json={"checkpoint": checkpoint}
    ).json()
    assert restored["standing"] == "ALIVE"
    assert client.delete(f"/episodes/{episode_id}").json()["standing"] == "ALIVE"
    assert client.get("/episodes/missing/observations/latest").status_code == 404
    assert client.post("/episodes", json={"provider": "missing"}).status_code == 404


@pytest.mark.asyncio
async def test_fastmcp_surface_executes_in_process() -> None:
    runtime = GymAct()
    runtime.register_provider(MemoryProvider())
    mcp = create_mcp(runtime)
    assert isinstance(mcp, FastMCP)
    async with Client(mcp) as client:
        tools = await client.list_tools()
        assert {tool.name for tool in tools} == {
            "discover",
            "create_episode",
            "observe",
            "act",
            "verify",
            "checkpoint",
            "restore",
            "teardown",
        }
        created = await client.call_tool(
            "create_episode", {"provider": "memory", "config": {"initial": {"x": 1}}}
        )
        episode_id = created.data["episode_id"]
        action = await client.call_tool(
            "act",
            {
                "episode_id": episode_id,
                "affordance": "set",
                "payload": {"key": "x", "value": 3},
                "idempotency_key": "mcp-set",
            },
        )
        assert action.data["accepted"] is True
        verified = await client.call_tool("verify", {"episode_id": episode_id, "expected": {"x": 3}})
        assert verified.data["passed"] is True


class _FakeBroker:
    def __init__(self) -> None:
        self.channels: list[str] = []

    def subscriber(self, channel: str):
        self.channels.append(f"sub:{channel}")
        return lambda fn: fn

    def publisher(self, channel: str):
        self.channels.append(f"pub:{channel}")
        return lambda fn: fn


def test_faststream_surface_is_broker_agnostic() -> None:
    runtime = GymAct()
    runtime.register_provider(MemoryProvider())
    assert isinstance(create_stream_app(None, runtime), FastStream)
    broker = _FakeBroker()
    bind_stream_handlers(broker, runtime)
    assert broker.channels == ["sub:gymact.commands", "pub:gymact.events"]


def test_typer_cli_version_profile_export_and_demo(tmp_path) -> None:
    runner = CliRunner()
    version = runner.invoke(cli_app, ["version"])
    assert version.exit_code == 0
    assert version.stdout.strip() == "26.8.7"
    profile = runner.invoke(cli_app, ["validate-profile"])
    assert profile.exit_code == 0
    payload = json.loads(profile.stdout)
    assert payload["conforms"] is True
    assert payload["custom_tbox_terms"] == []
    exported = runner.invoke(cli_app, ["export-profile", str(tmp_path)])
    assert exported.exit_code == 0
    assert (tmp_path / "profile.ttl").exists()
    denied = runner.invoke(cli_app, ["demo"])
    assert denied.exit_code == 0
    assert json.loads(denied.stdout)["actuation"]["standing"] == "REFUSED"
    allowed = runner.invoke(cli_app, ["demo", "--authority"])
    assert allowed.exit_code == 0
    assert json.loads(allowed.stdout)["actuation"]["standing"] == "ALIVE"
