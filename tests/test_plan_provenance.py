from __future__ import annotations

import pytest

from gymact import (
    AllowListAuthorityResolver,
    GymAct,
    MaterializationIntent,
    MemoryProvider,
    Standing,
)
from gymact.planning import (
    PlanProvenance,
    PlannedActuationIntent,
    execute_planned,
)

AUTHORITY = "urn:test:authority"
INCREMENT = "urn:gymact:memory:capability:increment"


async def _episode(runtime: GymAct, *, requires_authority: bool) -> str:
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


@pytest.mark.asyncio
async def test_planned_actuation_binds_exact_plan_to_exact_receipt_and_replays() -> None:
    runtime = GymAct(authority_resolver=AllowListAuthorityResolver({AUTHORITY}))
    episode_id = await _episode(runtime, requires_authority=True)
    intent = PlannedActuationIntent(
        episode_id=episode_id,
        capability=INCREMENT,
        payload={"key": "count", "amount": 1},
        authority_ref=AUTHORITY,
        idempotency_key="planned-once",
        plan_provenance=_plan(),
    )

    first = await execute_planned(runtime, intent)
    second = await execute_planned(runtime, intent)

    assert first == second
    assert first.actuation.accepted is True
    assert first.binding.plan_digest == intent.plan_provenance.digest
    assert first.binding.receipt_id == first.actuation.receipt.receipt_id
    assert (await runtime.observe(episode_id)).state == {"count": 1}


@pytest.mark.asyncio
async def test_plan_identity_participates_in_semantic_idempotency() -> None:
    runtime = GymAct(authority_resolver=AllowListAuthorityResolver({AUTHORITY}))
    episode_id = await _episode(runtime, requires_authority=True)
    common = dict(
        episode_id=episode_id,
        capability=INCREMENT,
        payload={"key": "count", "amount": 1},
        authority_ref=AUTHORITY,
        idempotency_key="same-key-different-plan",
    )

    first = await execute_planned(runtime, PlannedActuationIntent(**common, plan_provenance=_plan("1")))
    conflict = await execute_planned(
        runtime, PlannedActuationIntent(**common, plan_provenance=_plan("2"))
    )

    assert first.actuation.accepted is True
    assert conflict.actuation.standing == Standing.REFUSED
    assert conflict.actuation.receipt.reason == "IDEMPOTENCY_KEY_CONFLICT"
    assert first.binding.plan_digest != conflict.binding.plan_digest
    assert (await runtime.observe(episode_id)).state == {"count": 1}


@pytest.mark.asyncio
async def test_plan_authority_requirements_never_grant_live_authority() -> None:
    runtime = GymAct()
    episode_id = await _episode(runtime, requires_authority=True)
    result = await execute_planned(
        runtime,
        PlannedActuationIntent(
            episode_id=episode_id,
            capability=INCREMENT,
            payload={"key": "count", "amount": 1},
            authority_ref=AUTHORITY,
            idempotency_key="plan-is-not-authority",
            plan_provenance=_plan(),
        ),
    )

    assert result.actuation.accepted is False
    assert result.actuation.standing == Standing.REFUSED
    assert result.actuation.receipt.reason == "AUTHORITY_NOT_ADMITTED"
    assert (await runtime.observe(episode_id)).state == {"count": 0}
