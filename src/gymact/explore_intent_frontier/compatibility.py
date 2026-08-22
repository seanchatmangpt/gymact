from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .context import SelectionContext


class CompatibilityKind(StrEnum):
    EXACT = "EXACT"
    SEMANTIC_EQUIVALENT = "SEMANTIC_EQUIVALENT"
    BACKWARD_COMPATIBLE = "BACKWARD_COMPATIBLE"


@dataclass(frozen=True, slots=True)
class CompatibilityWitness:
    before_fingerprint: str
    after_fingerprint: str
    kind: CompatibilityKind
    evidence_id: str

    def __post_init__(self) -> None:
        if not self.evidence_id:
            raise ValueError("REFUSED_MISSING_COMPATIBILITY_EVIDENCE")


def admit_witness(
    before: SelectionContext, after: SelectionContext, witness: CompatibilityWitness
) -> None:
    if (
        witness.before_fingerprint != before.fingerprint
        or witness.after_fingerprint != after.fingerprint
    ):
        raise ValueError("REFUSED_COMPATIBILITY_WITNESS_MISMATCH")
    if before.subject != after.subject:
        raise ValueError("REFUSED_FOREIGN_CONTEXT_SUBJECT")
    if witness.kind is CompatibilityKind.EXACT and before != after:
        raise ValueError("REFUSED_FALSE_EXACT_COMPATIBILITY")
    if (
        witness.kind is CompatibilityKind.SEMANTIC_EQUIVALENT
        and (
            before.cut_digest != after.cut_digest
            or before.strategy != after.strategy
            or before.policy_digest != after.policy_digest
        )
    ):
        raise ValueError("REFUSED_UNPROVEN_SEMANTIC_EQUIVALENCE")
    if (
        witness.kind is CompatibilityKind.BACKWARD_COMPATIBLE
        and (before.cut_digest != after.cut_digest or before.strategy != after.strategy)
    ):
        raise ValueError("REFUSED_UNPROVEN_BACKWARD_COMPATIBILITY")
