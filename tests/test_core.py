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
    AuthorityDecision,
    Capability,
    Consequence,
    GymAct,
    MaterializationIntent,
    MemoryProvider,
    ProfileAuthority,
    ReceiptStage,
    RuntimeLimits,
    Standing,
)
from gymact.cli import app as cli_app
from gymact.models import AuthorityRequest
from gymact.providers import MEMORY_CAPABILITIES, MemoryEnvironment
from gymact.surfaces.fastapi import create_app
from gymact.surfaces.fastmcp import create_mcp
from gymact.surfaces.faststream import bind_stream_handlers, create_stream_app

AUTHORITY = "urn:test:authority"
SET_CAPABILITY = "urn:gymact:memory:capability:set"
DELETE_CAPABILITY = "urn:gymact:memory:capability:delete"
INCREMENT_CAPABILITY = "urn:gymact:memory:capability:increment"


def authorized_runtime(**kwargs: object) -> GymAct:
    return GymAct(
        authority_resolver=AllowListAuthorityResolver({AUTHORITY}),
        **kwargs,
    )


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
    assert result.receipt.receipt_digest is not None
    return result


def test_semantic_profile_is_public_ontology_only(tmp_path) -> None:
    authority = ProfileAuthority()
    result = authority.validate()
    assert result.conforms, result.report_text
    assert result.custom_tbox_terms == ()
    assert result.triple_count >= 50
    exported = authority.export(tmp_path)
    assert set(exported) == {"profile.ttl", "profile.shacl.ttl"}
    assert all(path.exists() and path.stat().st_size > 0 for path in exported.values())


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
    assert await runtime.verify_evidence_chain() is True


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
    assert first.receipt.prepared_receipt_digest is not None
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


class SlowAuthorityResolver:
    async def authorize(self, request: AuthorityRequest) -> AuthorityDecision:
        del request
        await anyio.sleep(0.05)
        return AuthorityDecision(admitted=True, reason="AUTHORITY_ADMITTED")


@pytest.mark.asyncio
async def test_authority_resolution_timeout_fails_closed() -> None:
    runtime = GymAct(
        authority_resolver=SlowAuthorityResolver(),
        limits=RuntimeLimits(authority_timeout_s=0.001),
    )
    runtime.register_provider(GuardedMaterializationProvider())
    result = await runtime.materialize(
        MaterializationIntent(
            provider="guarded-memory",
            authority_ref=AUTHORITY,
            idempotency_key="authority-timeout",
        )
    )
    assert result.standing == Standing.REFUSED
    assert result.receipt.reason == "AUTHORITY_RESOLUTION_TIMEOUT"


class BrokenMaterializationProvider(MemoryProvider):
    name = "broken-materialization"

    async def materialize(self, *, scenario, config):  # type: ignore[no-untyped-def]
        del scenario, config
        raise RuntimeError("secret provider detail must be hashed, not copied into receipt")


class SlowMaterializationProvider(MemoryProvider):
    name = "slow-materialization"

    async def materialize(self, *, scenario, config):  # type: ignore[no-untyped-def]
        await anyio.sleep(0.05)
        return await super().materialize(scenario=scenario, config=config)


@pytest.mark.asyncio
async def test_materialization_provider_error_and_timeout_are_receipted() -> None:
    runtime = GymAct(limits=RuntimeLimits(provider_timeout_s=0.001))
    runtime.register_provider(BrokenMaterializationProvider())
    runtime.register_provider(SlowMaterializationProvider())
    broken = await runtime.materialize(
        MaterializationIntent(
            provider="broken-materialization",
            idempotency_key="broken-materialization",
        )
    )
    assert broken.standing == Standing.BLOCKED
    assert broken.receipt.reason == "PROVIDER_ERROR"
    assert broken.receipt.error_type == "RuntimeError"
    assert broken.receipt.error_digest is not None
    assert "secret provider detail" not in broken.receipt.model_dump_json()
    timed = await runtime.materialize(
        MaterializationIntent(
            provider="slow-materialization",
            idempotency_key="slow-materialization",
        )
    )
    assert timed.standing == Standing.BLOCKED
    assert timed.receipt.reason == "PROVIDER_TIMEOUT"


@pytest.mark.asyncio
async def test_materialization_payload_and_state_limits_are_fail_closed() -> None:
    runtime = GymAct(limits=RuntimeLimits(max_payload_bytes=64, max_state_bytes=64))
    runtime.register_provider(MemoryProvider())
    refused = await runtime.materialize(
        MaterializationIntent(
            provider="memory",
            config={"initial": {"huge": "x" * 128}},
            idempotency_key="payload-too-large",
        )
    )
    assert refused.standing == Standing.REFUSED
    assert refused.receipt.reason == "PAYLOAD_LIMIT_EXCEEDED"

    state_limited = GymAct(limits=RuntimeLimits(max_payload_bytes=1024, max_state_bytes=32))
    state_limited.register_provider(MemoryProvider())
    blocked = await state_limited.materialize(
        MaterializationIntent(
            provider="memory",
            config={"initial": {"huge": "x" * 64}},
            idempotency_key="state-too-large",
        )
    )
    assert blocked.standing == Standing.BLOCKED
    assert blocked.receipt.reason.startswith("ENVIRONMENT_ADMISSION_FAILED")


@pytest.mark.asyncio
async def test_provider_authority_requirement_is_monotonic() -> None:
    runtime = GymAct()
    runtime.register_provider(MemoryProvider(requires_authority=True))
    result = await runtime.materialize(
        MaterializationIntent(
            provider="memory",
            config={"requires_authority": False},
            idempotency_key="cannot-downgrade-authority",
        )
    )
    assert result.episode is not None
    actuation = await runtime.act(
        ActuationIntent(
            episode_id=result.episode.episode_id,
            capability=SET_CAPABILITY,
            payload={"key": "safe", "value": True},
            idempotency_key="still-requires-authority",
        )
    )
    assert actuation.standing == Standing.REFUSED
    assert actuation.receipt.reason == "LIVE_AUTHORITY_REQUIRED"


@pytest.mark.asyncio
async def test_capabilities_are_semantic_identity_not_provider_binding() -> None:
    runtime = GymAct()
    runtime.register_provider(MemoryProvider())
    materialized = await materialize_memory(runtime, key="capability-materialize")
    episode = materialized.episode
    assert episode is not None
    capabilities = runtime.capabilities(episode.episode_id)
    assert capabilities == MEMORY_CAPABILITIES
    assert {item.iri for item in capabilities} == {
        SET_CAPABILITY,
        DELETE_CAPABILITY,
        INCREMENT_CAPABILITY,
    }
    validation = runtime.profile.validate_capabilities(capabilities)
    assert validation.conforms, validation.report_text


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
async def test_authorized_actuation_has_write_ahead_and_independent_verification() -> None:
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
    assert first.receipt.prepared_receipt_digest is not None
    receipts = await runtime.receipts(episode.episode_id)
    prepared = [
        item
        for item in receipts
        if item.operation.value == "act" and item.stage == ReceiptStage.PREPARED
    ]
    assert len(prepared) == 1
    assert prepared[0].receipt_digest == first.receipt.prepared_receipt_digest
    assert (await runtime.observe(episode.episode_id)).state == {"count": 1}
    verification = await runtime.verify(episode.episode_id, {"count": 1})
    assert verification.passed is True
    assert verification.receipt_id is not None
    assert await runtime.verify_evidence_chain() is True


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


class ReadCapabilityProvider(MemoryProvider):
    name = "read-capability"

    async def materialize(self, *, scenario, config):  # type: ignore[no-untyped-def]
        del scenario, config
        return ReadCapabilityEnvironment()


@pytest.mark.asyncio
async def test_unknown_and_read_capabilities_cannot_actuate() -> None:
    runtime = GymAct()
    runtime.register_provider(ReadCapabilityProvider())
    materialized = await runtime.materialize(
        MaterializationIntent(provider="read-capability", idempotency_key="read-materialize")
    )
    assert materialized.episode is not None
    episode_id = materialized.episode.episode_id
    unknown = await runtime.act(
        ActuationIntent(
            episode_id=episode_id,
            capability="urn:test:capability:missing",
            idempotency_key="unknown-capability",
        )
    )
    assert unknown.standing == Standing.UNSUPPORTED
    assert unknown.receipt.reason == "UNKNOWN_CAPABILITY"
    read = await runtime.act(
        ActuationIntent(
            episode_id=episode_id,
            capability="urn:test:capability:read",
            idempotency_key="read-as-actuation",
        )
    )
    assert read.standing == Standing.REFUSED
    assert read.receipt.reason == "READ_CAPABILITY_IS_NOT_ACTUATION"


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
async def test_idempotency_conflict_and_provider_error_do_not_claim_success() -> None:
    runtime = GymAct()
    runtime.register_provider(MemoryProvider())
    materialized = await materialize_memory(
        runtime, initial={"value": "text"}, key="provider-error-mat"
    )
    episode = materialized.episode
    assert episode is not None
    first = ActuationIntent(
        episode_id=episode.episode_id,
        capability=SET_CAPABILITY,
        payload={"key": "other", "value": 1},
        idempotency_key="same-key",
    )
    assert (await runtime.act(first)).accepted is True
    conflicting = first.model_copy(update={"payload": {"key": "other", "value": 2}})
    conflict = await runtime.act(conflicting)
    assert conflict.standing == Standing.REFUSED
    assert conflict.receipt.reason == "IDEMPOTENCY_KEY_CONFLICT"

    blocked = await runtime.act(
        ActuationIntent(
            episode_id=episode.episode_id,
            capability=INCREMENT_CAPABILITY,
            payload={"key": "value", "amount": 1},
            idempotency_key="bad-increment",
        )
    )
    assert blocked.accepted is False
    assert blocked.standing == Standing.BLOCKED
    assert blocked.receipt.reason == "PROVIDER_ERROR"
    assert blocked.receipt.error_type == "TypeError"
    assert blocked.receipt.error_digest is not None


@pytest.mark.asyncio
async def test_payload_limit_prevents_provider_actuation() -> None:
    runtime = GymAct(limits=RuntimeLimits(max_payload_bytes=32))
    runtime.register_provider(MemoryProvider())
    materialized = await materialize_memory(runtime, key="small-payload-materialize")
    episode = materialized.episode
    assert episode is not None
    result = await runtime.act(
        ActuationIntent(
            episode_id=episode.episode_id,
            capability=SET_CAPABILITY,
            payload={"key": "x", "value": "z" * 128},
            idempotency_key="huge-actuation",
        )
    )
    assert result.standing == Standing.REFUSED
    assert result.receipt.reason == "PAYLOAD_LIMIT_EXCEEDED"
    assert (await runtime.observe(episode.episode_id)).state == {}


@pytest.mark.asyncio
async def test_restore_and_teardown_reuse_authority_and_write_ahead() -> None:
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
    assert restored.prepared_receipt_digest is not None
    assert (await runtime.observe(episode.episode_id)).state == {"value": 1}
    torn_down = await runtime.teardown(episode.episode_id, authority_ref=AUTHORITY)
    assert torn_down.standing == Standing.ALIVE
    assert torn_down.prepared_receipt_digest is not None
    assert await runtime.teardown(episode.episode_id, authority_ref=AUTHORITY) == torn_down


def test_fastapi_surface_executes_real_episode_and_evidence_routes() -> None:
    runtime = GymAct()
    runtime.register_provider(MemoryProvider())
    client = TestClient(create_app(runtime))
    assert client.get("/health").json()["status"] == "ALIVE"
    assert client.get("/profile").json()["conforms"] is True
    assert client.get("/contract").json()["version"] == "26.8.7"
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
    payload = response.json()
    assert payload["accepted"] is True
    episode_id = payload["episode"]["episode_id"]
    capabilities = client.get(f"/episodes/{episode_id}/capabilities").json()["capabilities"]
    assert SET_CAPABILITY in {item["iri"] for item in capabilities}
    action = client.post(
        f"/episodes/{episode_id}/actions",
        json={
            "episode_id": episode_id,
            "capability": SET_CAPABILITY,
            "payload": {"key": "x", "value": 2},
            "idempotency_key": "api-set",
            "operation": "act",
        },
    )
    assert action.json()["accepted"] is True
    verification = client.post(f"/episodes/{episode_id}/verify", json={"expected": {"x": 2}})
    assert verification.json()["passed"] is True
    receipts = client.get(f"/episodes/{episode_id}/receipts").json()["receipts"]
    assert any(item["stage"] == "PREPARED" for item in receipts)
    assert "prov:" in client.get("/evidence/prov").text


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
            "contract",
            "create_episode",
            "capabilities",
            "observe",
            "act",
            "verify",
            "checkpoint",
            "restore",
            "teardown",
            "receipts",
            "provenance",
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
        action = await client.call_tool(
            "act",
            {
                "episode_id": episode_id,
                "capability": SET_CAPABILITY,
                "payload": {"key": "x", "value": 3},
                "idempotency_key": "mcp-set",
            },
        )
        assert action.data["accepted"] is True
        verified = await client.call_tool(
            "verify", {"episode_id": episode_id, "expected": {"x": 3}}
        )
        assert verified.data["passed"] is True
        evidence = await client.call_tool("receipts", {"episode_id": episode_id})
        assert len(evidence.data) >= 5


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


def test_typer_cli_version_profile_contract_and_demo(tmp_path) -> None:
    runner = CliRunner()
    version = runner.invoke(cli_app, ["version"])
    assert version.exit_code == 0
    assert version.stdout.strip() == "26.8.7"
    profile = runner.invoke(cli_app, ["validate-profile"])
    assert profile.exit_code == 0
    assert json.loads(profile.stdout)["conforms"] is True
    exported = runner.invoke(cli_app, ["export-profile", str(tmp_path / "profile")])
    assert exported.exit_code == 0
    contract_path = tmp_path / "contract.json"
    contract = runner.invoke(cli_app, ["export-contract", str(contract_path)])
    assert contract.exit_code == 0
    assert json.loads(contract_path.read_text())["version"] == "26.8.7"
    denied = runner.invoke(cli_app, ["demo"])
    assert denied.exit_code == 0
    denied_payload = json.loads(denied.stdout)
    assert denied_payload["actuation"]["standing"] == "REFUSED"
    assert denied_payload["evidence_chain_valid"] is True
    allowed = runner.invoke(cli_app, ["demo", "--authority"])
    assert allowed.exit_code == 0
    assert json.loads(allowed.stdout)["actuation"]["standing"] == "ALIVE"
