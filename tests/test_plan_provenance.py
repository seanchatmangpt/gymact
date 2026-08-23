from __future__ import annotations

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
from gymact.models import MaterializationIntent, Standing
from gymact.planning import PlanProvenance, bind_plan, execute_planned
from gymact.providers import MemoryProvider
from gymact.runtime import ProductionGymAct

AUTHORITY = "urn:test:authority"
INCREMENT = "urn:gymact:memory:capability:increment"


async def _episode(runtime: ProductionGymAct, *, requires_authority: bool) -> str:
    runtime.register_provider(MemoryProvider())
    result = await runtime.materialize(
        MaterializationIntent(
            provider="memory",
            config={"initial": {"count": 0}, "requires_authority": requires_authority},
            idempotency_key="planned-materialize",
        )
    )
    assert result.episode is not None
    return result.episode.episode_id


def _plan(version: str = "1") -> PlanProvenance:
    return PlanProvenance(
        plan_id="urn:test:plan:increment",
        plan_version=version,
        plan_step_id="increment-count",
        parent_step_ids=("observe-count",),
        precondition_digest="blake3:pre",
        postcondition_digest="blake3:post",
        required_authority_classes=("urn:test:authority-class:operator",),
    )


def _request(episode_id: str, idempotency_key: str) -> BrokerRequest:
    effect = ExpectedEffect(predicate="count", parameters={"value": 1})
    action = ActionDefinition(
        semantic_id="urn:test:action:increment",
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
            observer_ref="urn:test:observer",
            expected={"count": 1},
        ),
    )
    subject = SubjectRef(
        semantic_id="urn:test:memory-state",
        provider_ref="memory-state",
    )
    prepared = construct_prepared_action(
        action,
        episode_id=episode_id,
        subject=subject,
        payload={"key": "count", "amount": 1},
        admission_digest="admission",
        idempotency_key=idempotency_key,
    )
    grant = ExecutionGrant(
        principal="urn:test:principal",
        action_ref=action.semantic_id,
        subject=subject,
        capability_ref=action.capability_ref,
        authority_ref=AUTHORITY,
        policy_revision="policy-1",
        admitted_observation_ref="urn:test:observation",
        intended_effects=action.expected_effects,
        nonce="nonce",
    )
    return BrokerRequest(
        action=action,
        prepared=prepared,
        grant=grant,
        expected={"count": 1},
    )


@pytest.mark.asyncio
async def test_planned_brce_actuation_binds_exact_plan_and_replays_without_duplicate_do() -> None:
    runtime = ProductionGymAct(
        authority_resolver=AllowListAuthorityResolver({AUTHORITY})
    )
    episode_id = await _episode(runtime, requires_authority=True)
    broker = BRCEBroker(runtime)
    planned = bind_plan(_request(episode_id, "planned-once"), _plan())

    first = await execute_planned(broker, planned)
    second = await execute_planned(broker, planned)

    assert first.transition.standing is Standing.ALIVE
    assert second.transition.standing is Standing.ALIVE
    assert first.binding.plan_digest == planned.plan_provenance.digest
    assert first.transition.receipt.planning_provenance_digest == first.binding.plan_digest
    assert (
        first.transition.actuation.receipt.receipt_id
        == second.transition.actuation.receipt.receipt_id
    )
    assert (await runtime.observe(episode_id)).state == {"count": 1}


@pytest.mark.asyncio
async def test_plan_identity_participates_in_brce_semantic_idempotency() -> None:
    runtime = ProductionGymAct(
        authority_resolver=AllowListAuthorityResolver({AUTHORITY})
    )
    episode_id = await _episode(runtime, requires_authority=True)
    broker = BRCEBroker(runtime)
    request = _request(episode_id, "same-key-different-plan")

    first = await execute_planned(broker, bind_plan(request, _plan("1")))
    conflict = await execute_planned(broker, bind_plan(request, _plan("2")))

    assert first.transition.standing is Standing.ALIVE
    assert conflict.transition.standing is Standing.REFUSED
    assert conflict.transition.receipt.reason == "IDEMPOTENCY_KEY_CONFLICT"
    assert first.binding.plan_digest != conflict.binding.plan_digest
    assert conflict.transition.receipt.planning_provenance_digest == conflict.binding.plan_digest
    assert (await runtime.observe(episode_id)).state == {"count": 1}


@pytest.mark.asyncio
async def test_plan_authority_requirements_never_grant_live_authority() -> None:
    runtime = ProductionGymAct()
    episode_id = await _episode(runtime, requires_authority=True)
    broker = BRCEBroker(runtime)
    planned = bind_plan(_request(episode_id, "plan-is-not-authority"), _plan())

    result = await execute_planned(broker, planned)

    assert result.transition.standing is Standing.REFUSED
    assert result.transition.receipt.reason == "AUTHORITY_NOT_ADMITTED"
    assert result.transition.receipt.planning_provenance_digest == planned.plan_provenance.digest
    assert (await runtime.observe(episode_id)).state == {"count": 0}
