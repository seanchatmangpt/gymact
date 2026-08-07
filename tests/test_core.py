from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from fastmcp import FastMCP
from faststream import FastStream
from typer.testing import CliRunner

from gymact import ActuationIntent, GymAct, MemoryProvider, ProfileAuthority, Standing
from gymact.cli import app as cli_app
from gymact.surfaces.fastapi import create_app
from gymact.surfaces.fastmcp import create_mcp
from gymact.surfaces.faststream import create_stream_app


def test_semantic_profile_is_public_ontology_only() -> None:
    result = ProfileAuthority().validate()
    assert result.conforms, result.report_text
    assert result.custom_tbox_terms == ()
    assert result.triple_count >= 40


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
async def test_authorized_actuation_is_idempotent_and_independently_verified() -> None:
    runtime = GymAct()
    runtime.register_provider(MemoryProvider(requires_authority=True))
    episode = await runtime.create_episode("memory", config={"initial": {"count": 0}})
    intent = ActuationIntent(
        episode_id=episode.episode_id,
        affordance="increment",
        payload={"key": "count", "amount": 1},
        authority_ref="urn:test:authority",
        idempotency_key="increment-once",
    )
    first = await runtime.act(intent)
    second = await runtime.act(intent)
    assert first == second
    observation = await runtime.observe(episode.episode_id)
    assert observation.state["count"] == 1
    verification = await runtime.verify(episode.episode_id, {"count": 1})
    assert verification.passed is True
    assert first.receipt.verification_id is None


@pytest.mark.asyncio
async def test_checkpoint_restore_requires_same_authority_boundary() -> None:
    runtime = GymAct()
    runtime.register_provider(MemoryProvider(requires_authority=True))
    episode = await runtime.create_episode("memory", config={"initial": {"value": 1}})
    checkpoint = await runtime.checkpoint(episode.episode_id)
    await runtime.act(
        ActuationIntent(
            episode_id=episode.episode_id,
            affordance="set",
            payload={"key": "value", "value": 2},
            authority_ref="urn:test:authority",
        )
    )
    refused = await runtime.restore(episode.episode_id, checkpoint)
    assert refused.standing == Standing.REFUSED
    restored = await runtime.restore(
        episode.episode_id, checkpoint, authority_ref="urn:test:authority"
    )
    assert restored.standing == Standing.ALIVE
    assert (await runtime.observe(episode.episode_id)).state == {"value": 1}


def test_fastapi_surface_executes_real_episode() -> None:
    runtime = GymAct()
    runtime.register_provider(MemoryProvider())
    client = TestClient(create_app(runtime))
    assert client.get("/health").json()["status"] == "ALIVE"
    response = client.post("/episodes", json={"provider": "memory", "config": {"initial": {"x": 1}}})
    assert response.status_code == 200
    episode_id = response.json()["episode_id"]
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
    verification = client.post(f"/episodes/{episode_id}/verify", json={"expected": {"x": 2}})
    assert verification.json()["passed"] is True


def test_fastmcp_surface_constructs() -> None:
    runtime = GymAct()
    runtime.register_provider(MemoryProvider())
    assert isinstance(create_mcp(runtime), FastMCP)


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
    broker = _FakeBroker()
    app = create_stream_app(broker, runtime)
    assert isinstance(app, FastStream)
    assert broker.channels == ["sub:gymact.commands", "pub:gymact.events"]


def test_typer_cli_version_and_profile() -> None:
    runner = CliRunner()
    version = runner.invoke(cli_app, ["version"])
    assert version.exit_code == 0
    assert version.stdout.strip() == "26.8.7"
    profile = runner.invoke(cli_app, ["validate-profile"])
    assert profile.exit_code == 0
    payload = json.loads(profile.stdout)
    assert payload["conforms"] is True
    assert payload["custom_tbox_terms"] == []
