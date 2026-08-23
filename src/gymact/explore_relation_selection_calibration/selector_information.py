from __future__ import annotations

from dataclasses import dataclass
from math import log2

from .calibration import CalibrationEvidence
from .relation import Relation


@dataclass(frozen=True)
class InformationScore:
    relation: Relation
    entropy: float


def _binary_entropy(p: float) -> float:
    if p <= 0.0 or p >= 1.0:
        return 0.0
    return -(p * log2(p) + (1.0 - p) * log2(1.0 - p))


def rank_information(admitted: tuple[CalibrationEvidence, ...]) -> tuple[InformationScore, ...]:
    scores = []
    for e in admitted:
        error_mass = (e.false_positive + e.false_negative) / e.support
        scores.append(InformationScore(e.relation, _binary_entropy(error_mass)))
    return tuple(sorted(scores, key=lambda s: (-s.entropy, s.relation.value)))
