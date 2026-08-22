from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

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
    Capability,
    Consequence,
    GymAct,
    MaterializationIntent,
    MemoryProvider,
    ProfileAuthority,
    Standing,
)
from gymact.cli import app as cli_app
from gymact.ocel import validate_ocel_log, write_ocel_log
from gymact.providers import MemoryEnvironment
from gymact.surfaces.fastapi import create_app
from gymact.surfaces.fastmcp import create_mcp
from gymact.surfaces.faststream import bind_stream_handlers, create_stream_app

AUTHORITY = "urn:test:authority"
SET_CAPABILITY = "urn:gymact:memory:capability:set"
DELETE_CAPABILITY = "urn:gymact:memory:capability:delete"
INCREMENT_CAPABILITY = "urn:gymact:memory:capability:increment"


def authorized_runtime() -> GymAct:
    return GymAct(authority_resolver=AllowListAuthorityResolver({AUTHORITY}))


async def materialize_memory(
    runtime: GymAct,
    *,
    initial: dict[str, object] | None = None,
    requires_authority: bool = False,
    key: str = "materialize",
):
    result = await runtime.materialize(
        MaterializationIntent(
            provider="memory",
            config={
                "initial": initial or {},
                "requires_authority": requires_authority,
            },
            idempotency_key=key,
        )
    )
    assert result.accepted is True
    assert result.episode is not None
    assert result.observation is not None
    return result


def test_semantic_profile_is_public_ontology_only(tmp_path) -> None:
    authority = ProfileAuthority()
    result = authority.validate()
    assert result.conforms, result.report_text
    assert result.custom_tbox_terms == ()
    assert result.triple_count >= 50
    exported = authority.export(tmp_path)
    assert set(exported) == {"profile.ttl", "profile.shacl.ttl"}
    for resource in exported.values():
        assert resource.path.exists() and resource.path.stat().st_size > 0
        real_digest = hashlib.sha256(resource.path.read_bytes()).hexdigest()
        assert resource.sha256 == real_digest


def test_provider_registration_and_discovery() -> None:
    runtime = GymAct()
    runtime.register_provider(MemoryProvider())
    assert runtime.discover() == ("memory",)
    with pytest.raises(ValueError, match="provider already registered"):
        runtime.register_provider(MemoryProvider())
    with pytest.raises(TypeError, match="EnvironmentProvider"):
        runtime.register_provider(object())  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_unknown_provider_materialization_is_typed_not_exception() -> None:
    runtime = GymAct()
    result = await runtime.materialize(
        MaterializationIntent(provider="missing", idempotency_key="missing-provider")
    )
    assert result.accepted is False
    assert result.standing == Standing.UNSUPPORTED
    assert result.receipt.reason == "UNKNOWN_PROVIDER"


@pytest.mark.asyncio
async def test_materialization_is_idempotent_and_conflict_refused() -> None:
    runtime = GymAct()
    runtime.register_provider(MemoryProvider())
    intent = MaterializationIntent(
        provider="memory",
        config={"initial": {"x": 1}},
        idempotency_key="same-materialization",
    )
    first = await runtime.materialize(intent)
    second = await runtime.materialize(intent)
    assert first == second
    conflicting = intent.model_copy(update={"config": {"initial": {"x": 2}}})
    refused = await runtime.materialize(conflicting)
    assert refused.standing == Standing.REFUSED
    assert refused.receipt.reason == "IDEMPOTENCY_KEY_CONFLICT"


class GuardedMaterializationProvider(MemoryProvider):
    name = "guarded-memory"
    materialization_requires_authority = True


@pytest.mark.asyncio
async def test_materialization_authority_is_fail_closed_then_admitted() -> None:
    denied_runtime = GymAct()
    denied_runtime.register_provider(GuardedMaterializationProvider())
    denied = await denied_runtime.materialize(
        MaterializationIntent(
            provider="guarded-memory",
            authority_ref=AUTHORITY,
            idempotency_key="denied-materialize",
        )
    )
    assert denied.standing == Standing.REFUSED
    assert denied.receipt.reason == "AUTHORITY_NOT_ADMITTED"

    allowed_runtime = authorized_runtime()
    allowed_runtime.register_provider(GuardedMaterializationProvider())
    allowed = await allowed_runtime.materialize(
        MaterializationIntent(
            provider="guarded-memory",
            authority_ref=AUTHORITY,
            idempotency_key="allowed-materialize",
        )
    )
    assert allowed.standing == Standing.ALIVE
    assert allowed.episode is not None
    assert allowed.receipt.authority_evidence_ref is not None


class BrokenMaterializationProvider(MemoryProvider):
    name = "broken-materialization"

    async def materialize(self, *, scenario, config):  # type: ignore[no-untyped-def]
        del scenario, config
        raise RuntimeError("secret provider detail must be hashed, not copied into receipt")


@pytest.mark.asyncio
async def test_materialization_provider_error_is_bounded_and_receipted() -> None:
    runtime = GymAct()
    runtime.register_provider(BrokenMaterializationProvider())
    result = await runtime.materialize(
        MaterializationIntent(
            provider="broken-materialization",
            idempotency_key="broken-materialization",
        )
    )
    assert result.standing == Standing.BLOCKED
    assert result.receipt.reason == "PROVIDER_ERROR:RuntimeError"
    assert result.receipt.error_digest is not None
    assert "secret provider detail" not in result.receipt.reason


@pytest.mark.asyncio
async def test_capabilities_are_semantic_identity_not_provider_binding() -> None:
    runtime = GymAct()
    runtime.register_provider(MemoryProvider())
    materialized = await materialize_memory(runtime, key="capability-materialize")
    assert materialized.episode is not None
    capabilities = runtime.capabilities(materialized.episode.episode_id)
    assert {item.iri for item in capabilities} == {
        SET_CAPABILITY,
        DELETE_CAPABILITY,
        INCREMENT_CAPABILITY,
    }
    assert {item.binding for item in capabilities} == {"set", "delete", "increment"}
    validation = runtime.profile.validate_capabilities(capabilities)
    assert validation.conforms, validation.report_text


@pytest.mark.asyncio
async def test_authority_refusal_does_not_change_world() -> None:
    runtime = GymAct()
    runtime.register_provider(MemoryProvider())
    materialized = await materialize_memory(
        runtime,
        initial={"safe": False},
        requires_authority=True,
        key="authority-refusal-materialize",
    )
    episode = materialized.episode
    assert episode is not None
    result = await runtime.act(
        ActuationIntent(
            episode_id=episode.episode_id,
            capability=SET_CAPABILITY,
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
    runtime.register_provider(MemoryProvider())
    materialized = await materialize_memory(
        runtime,
        initial={"safe": False},
        requires_authority=True,
        key="authority-string-materialize",
    )
    episode = materialized.episode
    assert episode is not None
    result = await runtime.act(
        ActuationIntent(
            episode_id=episode.episode_id,
            capability=SET_CAPABILITY,
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
    runtime.register_provider(MemoryProvider())
    materialized = await materialize_memory(
        runtime,
        initial={"count": 0},
        requires_authority=True,
        key="authorized-materialize",
    )
    episode = materialized.episode
    assert episode is not None
    intent = ActuationIntent(
        episode_id=episode.episode_id,
        capability=INCREMENT_CAPABILITY,
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
async def test_unknown_capability_is_unsupported_without_provider_call() -> None:
    runtime = GymAct()
    runtime.register_provider(MemoryProvider())
    materialized = await materialize_memory(runtime, initial={"x": 1}, key="unknown-cap")
    episode = materialized.episode
    assert episode is not None
    result = await runtime.act(
        ActuationIntent(
            episode_id=episode.episode_id,
            capability="urn:test:capability:missing",
            idempotency_key="unknown-capability",
        )
    )
    assert result.standing == Standing.UNSUPPORTED
    assert result.receipt.reason == "UNKNOWN_CAPABILITY"
    assert (await runtime.observe(episode.episode_id)).state == {"x": 1}


class ReadCapabilityEnvironment(MemoryEnvironment):
    def capabilities(self) -> tuple[Capability, ...]:
        return (
            Capability(
                iri="urn:test:capability:read",
                title="Read-only capability",
                consequence=Consequence.READ,
                binding="read",
            ),
        )

    async def actuate(self, capability, payload):  # type: ignore[no-untyped-def]
        self._ensure_open()
        if capability.binding == "read":
            return {"capability": capability.iri, "result": deepcopy(self._state)}
        return await super().actuate(capability, payload)


class ReadCapabilityProvider(MemoryProvider):
    name = "read-capability"

    async def materialize(self, *, scenario, config):  # type: ignore[no-untyped-def]
        del scenario, config
        return ReadCapabilityEnvironment()


@pytest.mark.asyncio
async def test_read_capability_cannot_be_smuggled_through_actuation() -> None:
    runtime = GymAct()
    runtime.register_provider(ReadCapabilityProvider())
    result = await runtime.materialize(
        MaterializationIntent(provider="read-capability", idempotency_key="read-materialize")
    )
    assert result.episode is not None
    actuation = await runtime.act(
        ActuationIntent(
            episode_id=result.episode.episode_id,
            capability="urn:test:capability:read",
            idempotency_key="read-as-actuation",
        )
    )
    assert actuation.standing == Standing.REFUSED
    assert actuation.receipt.reason == "READ_CAPABILITY_IS_NOT_ACTUATION"


@pytest.mark.asyncio
async def test_read_invokes_a_real_read_capability_directly() -> None:
    """`read()` is the real, symmetric counterpart to `act()`'s DO-only
    law -- it must actually reach `ReadCapabilityEnvironment.actuate()`,
    not just refuse to raise."""
    runtime = GymAct()
    runtime.register_provider(ReadCapabilityProvider())
    result = await runtime.materialize(
        MaterializationIntent(provider="read-capability", idempotency_key="read-direct")
    )
    assert result.episode is not None
    outcome = await runtime.read(result.episode.episode_id, "urn:test:capability:read", {})
    assert outcome["capability"] == "urn:test:capability:read"


@pytest.mark.asyncio
async def test_do_capability_cannot_be_smuggled_through_read() -> None:
    """Mirror-image refusal: a real DO capability must not be reachable via
    `read()` either -- `read()` is READ-only by the same law `act()` is
    DO-only by."""
    runtime = GymAct(authority_resolver=AllowListAuthorityResolver({AUTHORITY}))
    runtime.register_provider(MemoryProvider())
    result = await runtime.materialize(
        MaterializationIntent(provider="memory", authority_ref=AUTHORITY)
    )
    assert result.episode is not None
    do_capability = next(
        c for c in runtime.capabilities(result.episode.episode_id) if c.consequence is Consequence.DO
    )
    with pytest.raises(ValueError, match="DO_CAPABILITY_IS_NOT_A_READ"):
        await runtime.read(result.episode.episode_id, do_capability.iri, {})


@pytest.mark.asyncio
async def test_read_unknown_capability_raises() -> None:
    runtime = GymAct()
    runtime.register_provider(ReadCapabilityProvider())
    result = await runtime.materialize(
        MaterializationIntent(provider="read-capability", idempotency_key="read-unknown")
    )
    assert result.episode is not None
    with pytest.raises(ValueError, match="unknown capability"):
        await runtime.read(result.episode.episode_id, "urn:test:capability:not-real", {})


@pytest.mark.asyncio
async def test_concurrent_same_intent_actuates_once() -> None:
    runtime = authorized_runtime()
    runtime.register_provider(MemoryProvider())
    materialized = await materialize_memory(
        runtime,
        initial={"count": 0},
        requires_authority=True,
        key="concurrent-materialize",
    )
    episode = materialized.episode
    assert episode is not None
    intent = ActuationIntent(
        episode_id=episode.episode_id,
        capability=INCREMENT_CAPABILITY,
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
    materialized = await materialize_memory(runtime, initial={"value": 0}, key="conflict-mat")
    episode = materialized.episode
    assert episode is not None
    first = ActuationIntent(
        episode_id=episode.episode_id,
        capability=SET_CAPABILITY,
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
async def test_provider_error_is_receipted_without_leaking_detail() -> None:
    runtime = GymAct()
    runtime.register_provider(MemoryProvider())
    materialized = await materialize_memory(
        runtime, initial={"value": "text"}, key="provider-error-mat"
    )
    episode = materialized.episode
    assert episode is not None
    result = await runtime.act(
        ActuationIntent(
            episode_id=episode.episode_id,
            capability=INCREMENT_CAPABILITY,
            payload={"key": "value", "amount": 1},
            idempotency_key="bad-increment",
        )
    )
    assert result.accepted is False
    assert result.standing == Standing.BLOCKED
    assert result.receipt.reason == "PROVIDER_ERROR:TypeError"
    assert result.receipt.error_digest is not None
    assert result.receipt.pre_state_digest == result.receipt.post_state_digest


@pytest.mark.asyncio
async def test_memory_delete_increment_verify_and_idempotent_teardown() -> None:
    runtime = GymAct()
    runtime.register_provider(MemoryProvider())
    materialized = await materialize_memory(
        runtime, initial={"x": 1, "drop": 2}, key="lifecycle-mat"
    )
    episode = materialized.episode
    assert episode is not None
    delete = await runtime.act(
        ActuationIntent(
            episode_id=episode.episode_id,
            capability=DELETE_CAPABILITY,
            payload={"key": "drop"},
            idempotency_key="delete",
        )
    )
    assert delete.accepted
    increment = await runtime.act(
        ActuationIntent(
            episode_id=episode.episode_id,
            capability=INCREMENT_CAPABILITY,
            payload={"key": "x", "amount": 3},
            idempotency_key="increment",
        )
    )
    assert increment.observation is not None
    assert increment.observation.state == {"x": 4}
    assert (await runtime.verify(episode.episode_id, {"x": 99})).passed is False
    receipt = await runtime.teardown(episode.episode_id)
    assert receipt.standing == Standing.ALIVE
    assert await runtime.teardown(episode.episode_id) == receipt
    with pytest.raises(KeyError, match="unknown episode"):
        await runtime.observe(episode.episode_id)


@pytest.mark.asyncio
async def test_real_episode_produces_a_valid_ocel_log_and_writes_the_conformance_fixture() -> None:
    """Van der Aalst item 1: instrument a real run as a real OCEL log.

    Drives the exact same real lifecycle as
    `test_memory_delete_increment_verify_and_idempotent_teardown` (materialize
    -> act x2 -> verify -> teardown, real `MemoryProvider`, no mocks), then
    asserts the runtime's own accumulated Receipt trail produces a real,
    schema-valid OCEL 2.0 log via `episode_ocel_log` -- pure wiring over
    `receipts_to_ocel`, nothing synthesized here.

    Also writes the real resulting log to `tests/fixtures/real_episode.ocel.json`
    via `write_ocel_log` (validates before writing, digests the exact bytes on
    disk) -- this is the real, captured fixture the ggen-side conformance test
    (`gymact_bridge_pack_e2e.rs` / a conformance sibling) discovers a DFG from
    and checks fitness/precision against.
    """
    runtime = GymAct()
    runtime.register_provider(MemoryProvider())
    materialized = await materialize_memory(
        runtime, initial={"x": 1, "drop": 2}, key="ocel-fixture-mat"
    )
    episode = materialized.episode
    assert episode is not None
    await runtime.act(
        ActuationIntent(
            episode_id=episode.episode_id,
            capability=DELETE_CAPABILITY,
            payload={"key": "drop"},
            idempotency_key="ocel-delete",
        )
    )
    await runtime.act(
        ActuationIntent(
            episode_id=episode.episode_id,
            capability=INCREMENT_CAPABILITY,
            payload={"key": "x", "amount": 3},
            idempotency_key="ocel-increment",
        )
    )
    await runtime.verify(episode.episode_id, {"x": 4})
    await runtime.teardown(episode.episode_id)

    receipts = runtime.episode_receipts(episode.episode_id)
    assert [r.operation.value for r in receipts] == [
        "materialize",
        "act",
        "act",
        "verify",
        "teardown",
    ]

    log = runtime.episode_ocel_log(episode.episode_id)
    validate_ocel_log(log)
    assert len(log["events"]) == len(receipts)
    assert {e["type"] for e in log["events"]} == {"materialize", "act", "verify", "teardown"}

    fixture_path = Path(__file__).parent / "fixtures" / "real_episode.ocel.json"
    written_log, digest = write_ocel_log(fixture_path, receipts)
    assert written_log == log
    assert len(digest) == 64
    assert fixture_path.is_file()


@pytest.mark.asyncio
async def test_checkpoint_restore_requires_admitted_authority() -> None:
    runtime = authorized_runtime()
    runtime.register_provider(MemoryProvider())
    materialized = await materialize_memory(
        runtime,
        initial={"value": 1},
        requires_authority=True,
        key="restore-mat",
    )
    episode = materialized.episode
    assert episode is not None
    checkpoint = await runtime.checkpoint(episode.episode_id)
    await runtime.act(
        ActuationIntent(
            episode_id=episode.episode_id,
            capability=SET_CAPABILITY,
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


def test_fastapi_surface_executes_real_episode_and_contract_routes(request) -> None:
    runtime = GymAct(authority_resolver=AllowListAuthorityResolver({AUTHORITY}))
    runtime.register_provider(MemoryProvider())
    client = TestClient(create_app(runtime))
    request.addfinalizer(client.close)
    assert client.get("/health").json()["status"] == "ALIVE"
    assert client.get("/profile").json()["conforms"] is True
    assert client.get("/providers").json() == {"providers": ["memory"]}
    response = client.post(
        "/episodes",
        json={
            "provider": "memory",
            "config": {"initial": {"x": 1}},
            "idempotency_key": "api-materialize",
            "operation": "materialize",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["accepted"] is True
    episode_id = payload["episode"]["episode_id"]
    capabilities = client.get(f"/episodes/{episode_id}/capabilities").json()["capabilities"]
    assert SET_CAPABILITY in {item["iri"] for item in capabilities}
    assert client.get(f"/episodes/{episode_id}/observations/latest").json()["state"] == {"x": 1}
    checkpoint = client.get(f"/episodes/{episode_id}/checkpoint").json()["checkpoint"]
    action = client.post(
        f"/episodes/{episode_id}/actions",
        json={
            "episode_id": episode_id,
            "capability": SET_CAPABILITY,
            "payload": {"key": "x", "value": 2},
            "idempotency_key": "api-set",
            "operation": "act",
            "authority_ref": AUTHORITY,
        },
    )
    assert action.status_code == 200
    assert action.json()["accepted"] is True
    mismatch = client.post(
        f"/episodes/{episode_id}/actions",
        json={"episode_id": "wrong", "capability": SET_CAPABILITY, "payload": {}},
    )
    assert mismatch.status_code == 409
    verification = client.post(f"/episodes/{episode_id}/verify", json={"expected": {"x": 2}})
    assert verification.json()["passed"] is True
    restored = client.post(
        f"/episodes/{episode_id}/restore",
        json={"checkpoint": checkpoint},
        params={"authority_ref": AUTHORITY},
    ).json()
    assert restored["standing"] == "ALIVE"
    assert (
        client.request(
            "DELETE", f"/episodes/{episode_id}", params={"authority_ref": AUTHORITY}
        ).json()["standing"]
        == "ALIVE"
    )
    assert client.get("/episodes/missing/observations/latest").status_code == 404
    unsupported = client.post(
        "/episodes",
        json={"provider": "missing", "idempotency_key": "missing-api"},
    ).json()
    assert unsupported["standing"] == "UNSUPPORTED"


@pytest.mark.asyncio
async def test_fastmcp_surface_executes_in_process() -> None:
    runtime = GymAct(authority_resolver=AllowListAuthorityResolver({AUTHORITY}))
    runtime.register_provider(MemoryProvider())
    mcp = create_mcp(runtime)
    assert isinstance(mcp, FastMCP)
    async with Client(mcp) as client:
        tools = await client.list_tools()
        assert {tool.name for tool in tools} == {
            "discover",
            "create_episode",
            "capabilities",
            "observe",
            "act",
            "verify",
            "checkpoint",
            "restore",
            "teardown",
            "probe_repo",
            "ggen_agent_catalog",
            "ggen_agent_frontier",
            "ggen_agent_invoke",
        }
        created = await client.call_tool(
            "create_episode",
            {
                "provider": "memory",
                "config": {"initial": {"x": 1}},
                "idempotency_key": "mcp-materialize",
            },
        )
        episode_id = created.data["episode"]["episode_id"]
        listed = await client.call_tool("capabilities", {"episode_id": episode_id})
        assert SET_CAPABILITY in {item["iri"] for item in listed.data}
        action = await client.call_tool(
            "act",
            {
                "episode_id": episode_id,
                "capability": SET_CAPABILITY,
                "payload": {"key": "x", "value": 3},
                "idempotency_key": "mcp-set",
                "authority_ref": AUTHORITY,
            },
        )
        assert action.data["accepted"] is True
        verified = await client.call_tool(
            "verify", {"episode_id": episode_id, "expected": {"x": 3}}
        )
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
    export_payload = json.loads(exported.stdout)
    assert export_payload["profile_uri"] == ProfileAuthority.profile_uri
    for name in ("profile.ttl", "profile.shacl.ttl"):
        exported_path = tmp_path / name
        assert exported_path.exists()
        real_digest = hashlib.sha256(exported_path.read_bytes()).hexdigest()
        assert export_payload["files"][name]["path"] == str(exported_path)
        assert export_payload["files"][name]["sha256"] == real_digest
    denied = runner.invoke(cli_app, ["demo"])
    assert denied.exit_code == 0
    assert json.loads(denied.stdout)["actuation"]["standing"] == "REFUSED"
    allowed = runner.invoke(cli_app, ["demo", "--authority"])
    assert allowed.exit_code == 0
    assert json.loads(allowed.stdout)["actuation"]["standing"] == "ALIVE"
