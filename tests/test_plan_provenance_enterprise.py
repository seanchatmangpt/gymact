from __future__ import annotations

import asyncio
from time import perf_counter

import pytest

from gymact.action_contract import (
    ActionDefinition,
    ExecutionGrant,
    ExpectedEffect,
    SubjectRef,
    VerificationKind,
    VerificationStrategy,
    construct_prepared_action,
)
from gymact.authority import AllowListAuthorityResolver
from gymact.brce import BRCEBroker, BrokerRequest
from gymact.evidence import digest
from gymact.models import MaterializationIntent, Standing
from gymact.planning import (
    PlanProvenance,
    PlanReceiptBinding,
    bind_plan,
    execute_planned,
)
from gymact.providers import MemoryProvider
from gymact.runtime import ProductionGymAct

AUTHORITY = "urn:fortune5:test:authority"
INCREMENT = "urn:gymact:memory:capability:increment"


async def _runtime(*, authorized: bool = True) -> tuple[ProductionGymAct, str]:
    runtime = ProductionGymAct(
        authority_resolver=(
            AllowListAuthorityResolver({AUTHORITY}) if authorized else None
        )
    )
    runtime.register_provider(MemoryProvider())
    result = await runtime.materialize(
        MaterializationIntent(
            provider="memory",
            config={"initial": {"count": 0}, "requires_authority": True},
            idempotency_key="fortune5-enterprise-materialize",
        )
    )
    assert result.episode is not None
    return runtime, result.episode.episode_id


def _plan(version: str) -> PlanProvenance:
    return PlanProvenance(
        plan_id="urn:fortune5:test:plan:increment",
        plan_version=version,
        plan_step_id="increment-count",
        parent_step_ids=("observe-count",),
        precondition_digest="blake3:pre",
        postcondition_digest="blake3:post",
        required_authority_classes=("urn:fortune5:authority-class:operator",),
    )


def _request(episode_id: str, key: str) -> BrokerRequest:
    effect = ExpectedEffect(predicate="count", parameters={"value": 1})
    action = ActionDefinition(
        semantic_id="urn:fortune5:test:action:increment",
        provider_ref="memory",
        capability_ref=INCREMENT,
        subject_type="schema:Thing",
        input_schema={
            "type": "object",
            "required": ["key", "amount"],
            "properties": {
                "key": {"type": "string"},
                "amount": {"type": "integer"},
            },
        },
        expected_effects=(effect,),
        verification=VerificationStrategy(
            kind=VerificationKind.EXACT_STATE,
            observer_ref="urn:fortune5:test:observer",
            expected={"count": 1},
        ),
    )
    subject = SubjectRef(
        semantic_id=f"urn:fortune5:test:episode:{episode_id}",
        provider_ref="memory",
    )
    prepared = construct_prepared_action(
        action,
        episode_id=episode_id,
        subject=subject,
        payload={"key": "count", "amount": 1},
        admission_digest="fortune5-admission",
        idempotency_key=key,
    )
    grant = ExecutionGrant(
        principal="urn:fortune5:test:principal",
        action_ref=action.semantic_id,
        subject=subject,
        capability_ref=action.capability_ref,
        authority_ref=AUTHORITY,
        policy_revision="fortune5-policy-v1",
        admitted_observation_ref="urn:fortune5:test:observation",
        intended_effects=action.expected_effects,
        nonce=f"nonce:{key}",
    )
    return BrokerRequest(
        action=action,
        prepared=prepared,
        grant=grant,
        expected={"count": 1},
    )


def _assert_binding_matches_transition(result: object, plan_digest: str) -> None:
    planned = result  # type: ignore[assignment]
    assert planned.binding.plan_digest == plan_digest
    assert planned.binding.receipt_id == planned.transition.receipt.receipt_id
    assert planned.binding.receipt_digest == digest(
        planned.transition.receipt.model_dump(mode="json")
    )


@pytest.mark.asyncio
async def test_128_concurrent_exact_replays_produce_one_consequence() -> None:
    runtime, episode_id = await _runtime()
    broker = BRCEBroker(runtime)
    planned = bind_plan(_request(episode_id, "concurrent-exact"), _plan("1"))

    results = await asyncio.gather(
        *(execute_planned(broker, planned) for _ in range(128))
    )

    assert all(result.transition.standing is Standing.ALIVE for result in results)
    # Exact semantic idempotency collapses all concurrent attempts onto one
    # underlying consequence/actuation receipt.
    assert len(
        {
            result.transition.actuation.receipt.receipt_id
            for result in results
            if result.transition.actuation is not None
        }
    ) == 1
    # Each replay is nevertheless a newly verified transition with its own
    # receipt and therefore its own plan->receipt binding. This is desirable:
    # replay evidence is not erased merely because the consequence was reused.
    assert len({result.transition.receipt.receipt_id for result in results}) == len(results)
    assert len({result.binding.binding_digest for result in results}) == len(results)
    for result in results:
        _assert_binding_matches_transition(result, planned.plan_provenance.digest)
    assert (await runtime.observe(episode_id)).state == {"count": 1}
    assert runtime.verify_evidence_chain()


@pytest.mark.asyncio
async def test_concurrent_plan_drift_can_never_double_actuate_same_key() -> None:
    runtime, episode_id = await _runtime()
    broker = BRCEBroker(runtime)
    request = _request(episode_id, "concurrent-drift")
    variants = tuple(
        bind_plan(request, _plan("1" if index % 2 == 0 else "2"))
        for index in range(128)
    )

    results = await asyncio.gather(
        *(execute_planned(broker, planned) for planned in variants)
    )

    alive = [result for result in results if result.transition.standing is Standing.ALIVE]
    refused = [
        result for result in results if result.transition.standing is Standing.REFUSED
    ]
    assert alive
    assert refused
    assert len({result.binding.plan_digest for result in alive}) == 1
    assert all(
        result.transition.receipt.reason == "IDEMPOTENCY_KEY_CONFLICT"
        for result in refused
    )
    assert len(
        {
            result.transition.actuation.receipt.receipt_id
            for result in alive
            if result.transition.actuation is not None
        }
    ) == 1
    assert (await runtime.observe(episode_id)).state == {"count": 1}
    assert runtime.verify_evidence_chain()


@pytest.mark.asyncio
async def test_one_thousand_replays_are_stable_and_bounded() -> None:
    runtime, episode_id = await _runtime()
    broker = BRCEBroker(runtime)
    planned = bind_plan(_request(episode_id, "thousand-replay"), _plan("1"))

    started = perf_counter()
    results = [await execute_planned(broker, planned) for _ in range(1_000)]
    elapsed = perf_counter() - started

    assert all(result.transition.standing is Standing.ALIVE for result in results)
    assert len(
        {
            result.transition.actuation.receipt.receipt_id
            for result in results
            if result.transition.actuation is not None
        }
    ) == 1
    assert len({result.transition.receipt.receipt_id for result in results}) == len(results)
    for result in results:
        _assert_binding_matches_transition(result, planned.plan_provenance.digest)
    assert (await runtime.observe(episode_id)).state == {"count": 1}
    assert runtime.verify_evidence_chain()
    # Anti-collapse budget only; detailed latency is emitted by the workflow benchmark.
    assert elapsed < 30.0


@pytest.mark.asyncio
async def test_128_concurrent_requests_without_authority_are_all_refused_without_do() -> None:
    runtime, episode_id = await _runtime(authorized=False)
    broker = BRCEBroker(runtime)
    planned = bind_plan(_request(episode_id, "no-authority"), _plan("1"))

    results = await asyncio.gather(
        *(execute_planned(broker, planned) for _ in range(128))
    )

    assert all(result.transition.standing is Standing.REFUSED for result in results)
    assert all(
        result.transition.receipt.reason == "AUTHORITY_NOT_ADMITTED"
        for result in results
    )
    assert all(result.transition.actuation is None for result in results)
    assert (await runtime.observe(episode_id)).state == {"count": 0}


def test_plan_binding_twenty_thousand_operations_has_no_catastrophic_regression() -> None:
    request = _request("offline-benchmark-episode", "bind-only")
    provenance = _plan("1")

    started = perf_counter()
    bindings = [bind_plan(request, provenance) for _ in range(20_000)]
    elapsed = perf_counter() - started

    assert all(
        binding.request.prepared.planning_provenance_digest == provenance.digest
        for binding in bindings
    )
    assert 20_000 / max(elapsed, 1e-9) > 1_000


@pytest.mark.asyncio
async def test_receipt_binding_refuses_tampered_plan_digest() -> None:
    runtime, episode_id = await _runtime()
    planned = bind_plan(_request(episode_id, "receipt-tamper"), _plan("1"))
    result = await execute_planned(BRCEBroker(runtime), planned)
    tampered = result.transition.receipt.model_copy(
        update={"planning_provenance_digest": _plan("tampered").digest}
    )

    with pytest.raises(ValueError, match="RECEIPT_PLAN_PROVENANCE_MISMATCH"):
        PlanReceiptBinding.manufacture(planned.plan_provenance, tampered)
