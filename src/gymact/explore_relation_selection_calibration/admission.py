from __future__ import annotations

from dataclasses import dataclass

from .calibration import CalibrationEvidence
from .confidence import error_upper
from .errors import Refused
from .metamorphic import MetamorphicWitness, require_lawful


@dataclass(frozen=True)
class AdmissionPolicy:
    min_support: int = 20
    max_false_equivalence_upper: float = 0.20
    max_false_refusal_upper: float = 0.30


def admit(
    e: CalibrationEvidence, witness: MetamorphicWitness, policy: AdmissionPolicy
) -> CalibrationEvidence:
    require_lawful(witness)
    if e.support < policy.min_support:
        raise Refused("INSUFFICIENT_CALIBRATION_SUPPORT", str(e.support))
    negatives = e.false_positive + e.true_negative
    positives = e.false_negative + e.true_positive
    if negatives and error_upper(e.false_positive, negatives) > policy.max_false_equivalence_upper:
        raise Refused("FALSE_EQUIVALENCE_BOUND_EXCEEDED", e.relation.value)
    if positives and error_upper(e.false_negative, positives) > policy.max_false_refusal_upper:
        raise Refused("FALSE_REFUSAL_BOUND_EXCEEDED", e.relation.value)
    return e
