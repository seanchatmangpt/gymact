from __future__ import annotations

from typing import Any

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
from gymact.crown_runtime import execute_admitted, execute_verified
from gymact.models import (
    ActuationIntent,
    ActuationResult,
    Operation,
    Receipt,
    Standing,
    VerificationResult,
)


class MechanicalRuntime:
    """Mechanics-only double; it cannot establish provider integration standing."""

    def __init__(
        self,
        actuation: ActuationResult,
        verification: VerificationResult,
    ) -> None:
        self.actuation = actuation
        self.verification = verification
        self.recorded: list[Receipt] = []

    async def act(self, intent: ActuationIntent) -> ActuationResult:
        del intent
        return self.actuation

    async def verify(
        self,
        episode_id: str,
        expected: dict[str, Any],
    ) -> VerificationResult:
        del episode_id, expected
        return self.verification

    def _record(self, receipt: Receipt) -> Receipt:
        self.recorded.append(receipt)
        return receipt


def actuation(
    *,
    accepted: bool = True,
    standing: Standing = Standing.ALIVE,
    pre: str = "before",
    post: str = "after",
    reason: str | None = None,
) -> ActuationResult:
    return ActuationResult(
        accepted=accepted,
        standing=standing,
        receipt=Receipt(
            episode_id="episode",
            operation=Operation.ACT,
            standing=standing,
            subject_ref="provider-subject",
            capability_ref="urn:capability:test",
            pre_state_digest=pre,
            post_state_digest=post,
            reason=reason,
        ),
    )


def verification(*, passed: bool) -> VerificationResult:
    return VerificationResult(
        episode_id="episode",
        passed=passed,
        expected={"value": 1},
        observed={"value": 1 if passed else 0},
        state_digest="after",
    )


def admitted_fixture() -> tuple[ActionDefinition, object, ExecutionGrant]:
    effect = ExpectedEffect(predicate="state", parameters={"value": 1})
    action = ActionDefinition(
        semantic_id="urn:action:set",
        provider_ref="urn:provider:test",
        capability_ref="urn:capability:test",
        subject_type="schema:Thing",
        input_schema={"type": "object", "required": ["value"]},
        expected_effects=(effect,),
        verification=VerificationStrategy(
            kind=VerificationKind.EXACT_STATE,
            observer_ref="urn:observer:test",
            expected={"value": 1},
        ),
    )
    subject = SubjectRef(
        semantic_id="urn:subject:1",
        provider_ref="provider-subject",
        revision="rev-1",
    )
    prepared = construct_prepared_action(
        action,
        episode_id="episode",
        subject=subject,
        payload={"value": 1},
        admission_digest="admission",
        idempotency_key="intent-1",
    )
    grant = ExecutionGrant(
        principal="urn:principal:test",
        delegated_principal="urn:principal:delegate",
        action_ref=action.semantic_id,
        subject=subject,
        capability_ref=action.capability_ref,
        authority_ref="urn:authority:test",
        policy_revision="policy-1",
        admitted_observation_ref="urn:observation:1",
        intended_effects=action.expected_effects,
        scope_refs=(subject.semantic_id,),
        nonce="nonce",
    )
    return action, prepared, grant


@pytest.mark.asyncio
async def test_admitted_success_binds_grant_and_parent_receipt() -> None:
    action, prepared, grant = admitted_fixture()
    runtime = MechanicalRuntime(actuation(), verification(passed=True))
    result = await execute_admitted(
        runtime,
        action,
        prepared,  # type: ignore[arg-type]
        grant,
        current_revision="rev-1",
        expected={"value": 1},
    )
    assert result.standing is Standing.ALIVE
    assert result.receipt.principal == grant.principal
    assert result.receipt.delegated_principal == grant.delegated_principal
    assert result.receipt.policy_revision == grant.policy_revision
    assert result.receipt.intended_effects == (
        {"predicate": "state", "parameters": {"value": 1}},
    )
    assert result.receipt.acknowledgement_status == "ACKNOWLEDGED"
    assert result.receipt.verified is True
    assert result.receipt.parent_receipt_ids


@pytest.mark.asyncio
async def test_uncertain_receipt_separates_ack_effect_and_verification() -> None:
    source = actuation(
        accepted=False,
        standing=Standing.BLOCKED,
        reason="ACTUATION_TIMEOUT",
    )
    runtime = MechanicalRuntime(source, verification(passed=False))
    result = await execute_verified(
        runtime,
        ActuationIntent(
            episode_id="episode",
            capability="urn:capability:test",
            idempotency_key="intent-1",
        ),
        {"value": 1},
    )
    assert result.standing is Standing.UNCERTAIN
    assert result.receipt.acknowledgement_status == "LOST"
    assert result.receipt.world_changed is True
    assert result.receipt.verified is False
    assert result.receipt.parent_receipt_ids == (source.receipt.receipt_id,)
