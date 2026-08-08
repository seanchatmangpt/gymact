"""Execution capsules for defensible local ALIVE reuse without subject overclaiming."""
from __future__ import annotations

from pydantic import Field

from gymact.evidence import digest
from gymact.models import FrozenModel, Standing


class CapsuleIdentity(FrozenModel):
    """All identities that must match before verifier evidence is reusable."""

    source_digest: str = Field(min_length=1)
    validator_digest: str = Field(min_length=1)
    toolchain_digest: str = Field(min_length=1)
    config_digest: str = Field(min_length=1)
    environment_digest: str = Field(min_length=1)

    @property
    def capsule_digest(self) -> str:
        return digest(self.model_dump(mode="json"))


class ValidationPack(FrozenModel):
    command: str = Field(min_length=1)
    exit_code: int
    evidence_refs: tuple[str, ...]
    standing: Standing


class VerifierCapsuleReceipt(FrozenModel):
    capsule: CapsuleIdentity
    validation: ValidationPack
    receipt_ref: str = Field(min_length=1)


class SubjectCapsuleReceipt(FrozenModel):
    capsule: CapsuleIdentity
    subject_digest: str = Field(min_length=1)
    executed: bool
    verified: bool
    standing: Standing
    receipt_ref: str = Field(min_length=1)


class CapsuleReuseDecision(FrozenModel):
    verifier_reusable: bool
    subject_reusable: bool
    standing: Standing
    reason: str


def evaluate_capsule_reuse(
    cached_verifier: VerifierCapsuleReceipt,
    current: CapsuleIdentity,
    *,
    cached_subject: SubjectCapsuleReceipt | None = None,
    subject_digest: str | None = None,
) -> CapsuleReuseDecision:
    """Reuse validator evidence only under exact capsule identity.

    SUBJECT_ALIVE is intentionally stricter: it requires the exact same subject digest
    and a prior executed+verified ALIVE subject receipt. Reusing verifier evidence never
    silently crowns a different subject.
    """
    if cached_verifier.capsule != current:
        return CapsuleReuseDecision(
            verifier_reusable=False,
            subject_reusable=False,
            standing=Standing.STALE,
            reason="CAPSULE_IDENTITY_DRIFT",
        )
    if (
        cached_verifier.validation.exit_code != 0
        or cached_verifier.validation.standing is not Standing.ALIVE
        or not cached_verifier.validation.evidence_refs
    ):
        return CapsuleReuseDecision(
            verifier_reusable=False,
            subject_reusable=False,
            standing=Standing.PARTIAL_ALIVE,
            reason="VERIFIER_CAPSULE_NOT_ALIVE",
        )

    subject_reusable = bool(
        cached_subject is not None
        and subject_digest is not None
        and cached_subject.capsule == current
        and cached_subject.subject_digest == subject_digest
        and cached_subject.executed
        and cached_subject.verified
        and cached_subject.standing is Standing.ALIVE
    )
    return CapsuleReuseDecision(
        verifier_reusable=True,
        subject_reusable=subject_reusable,
        standing=Standing.ALIVE if subject_reusable else Standing.STRUCTURAL,
        reason=(
            "EXACT_VERIFIER_AND_SUBJECT_CAPSULE_REUSABLE"
            if subject_reusable
            else "VERIFIER_REUSABLE_SUBJECT_EXECUTION_STILL_REQUIRED"
        ),
    )
