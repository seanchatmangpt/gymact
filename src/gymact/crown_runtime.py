"""Verified-consequence execution and reconciliation above the generic GymAct kernel.

The generic kernel proves that an admitted capability invocation ran and records an
independent post-observation. Crown execution adds the separate objective-verification
step required before a transition itself receives ALIVE standing.
"""

from __future__ import annotations

from typing import Any, Protocol

from gymact.action_contract import (
    ActionDefinition,
    ExecutionGrant,
    PreparedAction,
    ReconciliationDisposition,
    ReconciliationResult,
    admit_execution,
)
from gymact.models import (
    ActuationIntent,
    ActuationResult,
    FrozenModel,
    Operation,
    Receipt,
    Standing,
    VerificationResult,
)


class CrownRuntimeLike(Protocol):
    async def act(self, intent: ActuationIntent) -> ActuationResult: ...

    async def verify(
        self, episode_id: str, expected: dict[str, Any]
    ) -> VerificationResult: ...

    def _record(self, receipt: Receipt) -> Receipt: ...


class VerifiedTransition(FrozenModel):
    """One candidate DO path with objective-verification standing kept explicit."""

    standing: Standing
    actuation: ActuationResult
    verification: VerificationResult | None = None
    receipt: Receipt


class ReconciledTransition(FrozenModel):
    """Observed disposition of a prior uncertain execution; never an implicit retry."""

    reconciliation: ReconciliationResult
    verification: VerificationResult
    receipt: Receipt


def _possible_unacknowledged_effect(result: ActuationResult) -> bool:
    receipt = result.receipt
    if receipt.reason == "ACTUATION_TIMEOUT":
        return True
    return (
        not result.accepted
        and receipt.pre_state_digest is not None
        and receipt.post_state_digest is not None
        and receipt.pre_state_digest != receipt.post_state_digest
    )


def _verification_receipt(
    *,
    actuation: ActuationResult,
    verification: VerificationResult,
    standing: Standing,
    reason: str | None,
) -> Receipt:
    source = actuation.receipt
    return Receipt(
        episode_id=source.episode_id,
        operation=Operation.VERIFY,
        standing=standing,
        subject_ref=source.subject_ref,
        capability_ref=source.capability_ref,
        authority_ref=source.authority_ref,
        authority_evidence_ref=source.authority_evidence_ref,
        idempotency_key=source.idempotency_key,
        pre_state_digest=source.pre_state_digest,
        post_state_digest=verification.state_digest,
        verification_id=verification.verification_id,
        reason=reason,
    )


async def execute_verified(
    runtime: CrownRuntimeLike,
    intent: ActuationIntent,
    expected: dict[str, Any],
) -> VerifiedTransition:
    """DO then independently verify; only the verified transition may be Crown ALIVE."""

    actuation = await runtime.act(intent)
    if not actuation.accepted:
        if _possible_unacknowledged_effect(actuation):
            uncertain = Receipt(
                episode_id=actuation.receipt.episode_id,
                operation=Operation.ACT,
                standing=Standing.UNCERTAIN,
                subject_ref=actuation.receipt.subject_ref,
                capability_ref=actuation.receipt.capability_ref,
                authority_ref=actuation.receipt.authority_ref,
                authority_evidence_ref=actuation.receipt.authority_evidence_ref,
                idempotency_key=actuation.receipt.idempotency_key,
                pre_state_digest=actuation.receipt.pre_state_digest,
                post_state_digest=actuation.receipt.post_state_digest,
                error_digest=actuation.receipt.error_digest,
                reason="ACTUATION_OUTCOME_UNCERTAIN",
            )
            runtime._record(uncertain)
            return VerifiedTransition(
                standing=Standing.UNCERTAIN,
                actuation=actuation,
                receipt=uncertain,
            )
        return VerifiedTransition(
            standing=actuation.standing,
            actuation=actuation,
            receipt=actuation.receipt,
        )

    verification = await runtime.verify(intent.episode_id, expected)
    standing = Standing.ALIVE if verification.passed else Standing.REFUSED
    receipt = _verification_receipt(
        actuation=actuation,
        verification=verification,
        standing=standing,
        reason=None if verification.passed else "POSTCONDITION_FAILED",
    )
    runtime._record(receipt)
    return VerifiedTransition(
        standing=standing,
        actuation=actuation,
        verification=verification,
        receipt=receipt,
    )


async def reconcile_uncertain(
    runtime: CrownRuntimeLike,
    transition: VerifiedTransition,
    expected: dict[str, Any],
) -> ReconciledTransition:
    """Observe/verify an uncertain execution. This function never performs a retry."""

    if transition.standing is not Standing.UNCERTAIN:
        raise ValueError("RECONCILIATION_REQUIRES_UNCERTAIN_TRANSITION")

    verification = await runtime.verify(transition.actuation.receipt.episode_id, expected)
    source = transition.actuation.receipt
    if verification.passed:
        disposition = ReconciliationDisposition.EFFECT_CONFIRMED
        standing = Standing.ALIVE
        reason = "RECONCILIATION_EFFECT_CONFIRMED"
    elif (
        source.pre_state_digest is not None
        and verification.state_digest == source.pre_state_digest
    ):
        disposition = ReconciliationDisposition.NO_EFFECT
        standing = Standing.REFUSED
        reason = "RECONCILIATION_NO_EFFECT_RETRY_NOT_ADMITTED"
    else:
        disposition = ReconciliationDisposition.PARTIAL_EFFECT
        standing = Standing.UNCERTAIN
        reason = "RECONCILIATION_PARTIAL_EFFECT"

    reconciliation = ReconciliationResult(
        disposition=disposition,
        standing=standing,
        observed_state_digest=verification.state_digest,
        verification_ref=verification.verification_id,
        retry_admitted=False,
        reason=reason,
    )
    receipt = _verification_receipt(
        actuation=transition.actuation,
        verification=verification,
        standing=standing,
        reason=reason,
    )
    runtime._record(receipt)
    return ReconciledTransition(
        reconciliation=reconciliation,
        verification=verification,
        receipt=receipt,
    )


async def execute_admitted(
    runtime: CrownRuntimeLike,
    action: ActionDefinition,
    prepared: PreparedAction,
    grant: ExecutionGrant,
    *,
    current_revision: str | None,
    expected: dict[str, Any],
) -> VerifiedTransition:
    """Bridge CONSTRUCT to DO only after identity/revision admission closes."""
    admission = admit_execution(
        action,
        prepared,
        grant,
        current_revision=current_revision,
    )
    if not admission.admitted:
        receipt = Receipt(
            episode_id=prepared.episode_id,
            operation=Operation.ACT,
            standing=Standing.REFUSED,
            subject_ref=prepared.subject.provider_ref,
            capability_ref=action.capability_ref,
            authority_ref=grant.authority_ref,
            idempotency_key=prepared.idempotency_key,
            reason=admission.reason,
        )
        runtime._record(receipt)
        actuation = ActuationResult(
            accepted=False,
            standing=Standing.REFUSED,
            receipt=receipt,
        )
        return VerifiedTransition(
            standing=Standing.REFUSED,
            actuation=actuation,
            receipt=receipt,
        )

    intent = ActuationIntent(
        episode_id=prepared.episode_id,
        capability=action.capability_ref,
        payload=prepared.payload,
        authority_ref=grant.authority_ref,
        idempotency_key=prepared.idempotency_key,
    )
    return await execute_verified(runtime, intent, expected)
