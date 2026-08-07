from __future__ import annotations

import anyio
import pytest
from rdflib import RDF, Namespace

from gymact import (
    ActuationIntent,
    AuthorityDecision,
    BinaryVerificationScorer,
    GymAct,
    MaterializationIntent,
    MemoryProvider,
    RuntimeLimits,
    Standing,
    build_contract,
    load_provider_plugin,
    score_verification,
)
from gymact.providers import MemoryEnvironment

SET_CAPABILITY = "urn:gymact:memory:capability:set"


@pytest.mark.asyncio
async def test_authority_requirement_cannot_be_downgraded_by_scenario_config() -> None:
    provider = MemoryProvider(requires_authority=True)
    environment = await provider.materialize(
        scenario=None,
        config={"requires_authority": False},
    )
    assert environment.requires_authority is True


@pytest.mark.asyncio
async def test_receipts_form_verified_blake3_chain_and_idempotent_replay_is_not_new_do() -> None:
    runtime = GymAct()
    runtime.register_provider(MemoryProvider())
    materialized = await runtime.materialize(
        MaterializationIntent(
            provider="memory",
            config={"initial": {"x": 0}},
            idempotency_key="sota-materialize",
        )
    )
    assert materialized.episode is not None
    intent = ActuationIntent(
        episode_id=materialized.episode.episode_id,
        capability=SET_CAPABILITY,
        payload={"key": "x", "value": 1},
        idempotency_key="sota-act",
    )
    first = await runtime.act(intent)
    second = await runtime.act(intent)
    assert first == second
    records = runtime.evidence_records()
    assert len(records) == 2
    assert records[0].previous_digest is None
    assert records[1].previous_digest == records[0].record_digest
    assert len(records[0].record_digest) == 64
    assert runtime.verify_evidence_chain() is True
    assert runtime.receipt_record(first.receipt.receipt_id) == records[1]


@pytest.mark.asyncio
async def test_input_limit_refuses_before_provider_actuation() -> None:
    runtime = GymAct(limits=RuntimeLimits(max_input_bytes=1024))
    runtime.register_provider(MemoryProvider())
    materialized = await runtime.materialize(
        MaterializationIntent(provider="memory", idempotency_key="limit-materialize")
    )
    assert materialized.episode is not None
    result = await runtime.act(
        ActuationIntent(
            episode_id=materialized.episode.episode_id,
            capability=SET_CAPABILITY,
            payload={"key": "x", "value": "z" * 2048},
            idempotency_key="oversized-act",
        )
    )
    assert result.standing == Standing.REFUSED
    assert result.receipt.reason == "INPUT_LIMIT_EXCEEDED"
    assert (await runtime.observe(materialized.episode.episode_id)).state == {}


class _SlowAuthority:
    async def authorize(self, request):  # type: ignore[no-untyped-def]
        del request
        await anyio.sleep(0.05)
        return AuthorityDecision(admitted=True, reason="SHOULD_NOT_COMPLETE")


@pytest.mark.asyncio
async def test_authority_timeout_blocks_without_do() -> None:
    runtime = GymAct(
        authority_resolver=_SlowAuthority(),
        limits=RuntimeLimits(authority_timeout_s=0.005),
    )
    runtime.register_provider(MemoryProvider())
    materialized = await runtime.materialize(
        MaterializationIntent(
            provider="memory",
            config={"initial": {"safe": False}, "requires_authority": True},
            idempotency_key="authority-timeout-materialize",
        )
    )
    assert materialized.episode is not None
    result = await runtime.act(
        ActuationIntent(
            episode_id=materialized.episode.episode_id,
            capability=SET_CAPABILITY,
            payload={"key": "safe", "value": True},
            authority_ref="urn:test:authority",
            idempotency_key="authority-timeout-act",
        )
    )
    assert result.standing == Standing.BLOCKED
    assert result.receipt.reason == "AUTHORITY_TIMEOUT"
    assert (await runtime.observe(materialized.episode.episode_id)).state == {"safe": False}


class _SlowActEnvironment(MemoryEnvironment):
    async def actuate(self, capability, payload):  # type: ignore[no-untyped-def]
        await anyio.sleep(0.05)
        return await super().actuate(capability, payload)


class _SlowActProvider(MemoryProvider):
    name = "slow-act"

    async def materialize(self, *, scenario, config):  # type: ignore[no-untyped-def]
        del scenario, config
        return _SlowActEnvironment(initial={"x": 0})


@pytest.mark.asyncio
async def test_actuation_timeout_is_blocked_and_receipted() -> None:
    runtime = GymAct(limits=RuntimeLimits(actuate_timeout_s=0.005))
    runtime.register_provider(_SlowActProvider())
    materialized = await runtime.materialize(
        MaterializationIntent(provider="slow-act", idempotency_key="slow-materialize")
    )
    assert materialized.episode is not None
    result = await runtime.act(
        ActuationIntent(
            episode_id=materialized.episode.episode_id,
            capability=SET_CAPABILITY,
            payload={"key": "x", "value": 1},
            idempotency_key="slow-act",
        )
    )
    assert result.standing == Standing.BLOCKED
    assert result.receipt.reason == "ACTUATION_TIMEOUT"
    assert (await runtime.observe(materialized.episode.episode_id)).state == {"x": 0}


@pytest.mark.asyncio
async def test_public_prov_earl_projection_and_scoring_remain_distinct() -> None:
    runtime = GymAct()
    runtime.register_provider(MemoryProvider())
    materialized = await runtime.materialize(
        MaterializationIntent(
            provider="memory",
            config={"initial": {"ok": True}},
            idempotency_key="rdf-materialize",
        )
    )
    assert materialized.episode is not None
    verification = await runtime.verify(materialized.episode.episode_id, {"ok": True})
    scores = score_verification(verification, BinaryVerificationScorer())
    assert verification.passed is True
    assert scores[0].value == 1.0
    assert scores[0].metric == "goal_satisfaction"

    graph = runtime.evidence_rdf()
    prov = Namespace("http://www.w3.org/ns/prov#")
    earl = Namespace("http://www.w3.org/ns/earl#")
    assert any(graph.triples((None, RDF.type, prov.Entity)))
    assert any(graph.triples((None, RDF.type, earl.Assertion)))


def test_runtime_contract_is_self_digested_and_keeps_evidence_backed_operation_surface() -> None:
    contract = build_contract()
    assert contract.digest_algorithm == "blake3-256"
    assert contract.operations == (
        "discover",
        "materialize",
        "observe",
        "act",
        "verify",
        "checkpoint",
        "restore",
        "teardown",
    )
    assert len(contract.contract_digest) == 64
    assert "fastmcp" in contract.surfaces
    assert "faststream" in contract.surfaces


def test_missing_provider_plugin_is_typed_unsupported_not_exception() -> None:
    result = load_provider_plugin("__gymact_missing_provider__")
    assert result.standing == Standing.UNSUPPORTED
    assert result.provider is None
