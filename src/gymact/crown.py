"""Crown admission: bind consequential evidence before comparative standing."""
from __future__ import annotations

from pydantic import Field

from gymact.capsule import CapsuleIdentity
from gymact.crown_runtime import VerifiedTransition
from gymact.evidence import digest
from gymact.models import FrozenModel, Standing
from gymact.sota import FrontierResult, StandingEvidence


class CrownAdmissionError(ValueError):
    """Typed refusal for evidence that cannot acquire crown standing."""


class CrownEvidence(FrozenModel):
    """Exact evidence dimensions required to promote a run to Crown ALIVE."""

    subject_digest: str = Field(min_length=1)
    experiment_digest: str = Field(min_length=1)
    admitted_observation_digest: str = Field(min_length=1)
    authority_evidence_ref: str = Field(min_length=1)
    consequence_digest: str = Field(min_length=1)
    verifier_digest: str = Field(min_length=1)
    receipt_digest: str = Field(min_length=1)
    replay_receipt_digest: str = Field(min_length=1)
    observed: bool
    admitted: bool
    executed: bool
    changed: bool | None = None
    verified: bool
    replayed: bool

    @property
    def crown_digest(self) -> str:
        return digest(self.model_dump(mode="json"))

    def admit(self) -> None:
        failures: list[str] = []
        if not self.observed:
            failures.append("OBSERVATION_NOT_OBSERVED")
        if not self.admitted:
            failures.append("OBSERVATION_NOT_ADMITTED")
        if not self.executed:
            failures.append("SUBJECT_NOT_EXECUTED")
        if not self.verified:
            failures.append("CONSEQUENCE_NOT_VERIFIED")
        if not self.replayed:
            failures.append("REPLAY_NOT_VERIFIED")
        if failures:
            raise CrownAdmissionError("REFUSED:CROWN:" + ",".join(failures))


class CrownReceipt(FrozenModel):
    """Replayable binding between one execution capsule and Crown evidence."""

    capsule: CapsuleIdentity
    evidence: CrownEvidence
    transition_receipt_id: str = Field(min_length=1)
    standing: Standing

    @property
    def receipt_digest(self) -> str:
        return digest(self.model_dump(mode="json"))

    def admit(self) -> None:
        self.evidence.admit()
        if self.standing is not Standing.ALIVE:
            raise CrownAdmissionError("REFUSED:CROWN:STANDING_NOT_ALIVE")


def crown_transition(
    transition: VerifiedTransition,
    *,
    capsule: CapsuleIdentity,
    subject_digest: str,
    experiment_digest: str,
    admitted_observation_digest: str,
    verifier_digest: str,
    replay_receipt_digest: str,
    replayed: bool,
) -> CrownReceipt:
    """Promote only an actually verified, authority-bound transition to Crown evidence."""
    receipt = transition.receipt
    authority_ref = receipt.authority_evidence_ref or receipt.authority_ref
    if not authority_ref:
        raise CrownAdmissionError("REFUSED:CROWN:MISSING_AUTHORITY_EVIDENCE")
    if transition.standing is not Standing.ALIVE or transition.verification is None:
        raise CrownAdmissionError("REFUSED:CROWN:TRANSITION_NOT_ALIVE")
    if not transition.verification.passed or not receipt.verified:
        raise CrownAdmissionError("REFUSED:CROWN:CONSEQUENCE_NOT_VERIFIED")
    if not receipt.post_state_digest:
        raise CrownAdmissionError("REFUSED:CROWN:MISSING_CONSEQUENCE_DIGEST")

    evidence = CrownEvidence(
        subject_digest=subject_digest,
        experiment_digest=experiment_digest,
        admitted_observation_digest=admitted_observation_digest,
        authority_evidence_ref=authority_ref,
        consequence_digest=receipt.post_state_digest,
        verifier_digest=verifier_digest,
        receipt_digest=receipt.record_digest or digest(receipt.model_dump(mode="json")),
        replay_receipt_digest=replay_receipt_digest,
        observed=True,
        admitted=True,
        executed=True,
        changed=receipt.world_changed,
        verified=True,
        replayed=replayed,
    )
    evidence.admit()
    result = CrownReceipt(
        capsule=capsule,
        evidence=evidence,
        transition_receipt_id=receipt.receipt_id,
        standing=Standing.ALIVE,
    )
    result.admit()
    return result


def frontier_result_from_crown(
    crown: CrownReceipt,
    *,
    result_id: str,
    metrics: dict[str, float],
) -> FrontierResult:
    """Project a Crown receipt into the bounded SOTA algebra without losing bindings."""
    crown.admit()
    evidence = StandingEvidence(
        subject_digest=crown.evidence.subject_digest,
        experiment_digest=crown.evidence.experiment_digest,
        receipt_digest=crown.receipt_digest,
        verifier_digest=crown.evidence.verifier_digest,
        replay_verified=crown.evidence.replayed,
    )
    result = FrontierResult(result_id=result_id, evidence=evidence, metrics=metrics)
    result.admit()
    return result
