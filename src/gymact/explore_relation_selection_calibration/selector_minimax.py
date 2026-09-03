from __future__ import annotations

from dataclasses import dataclass

from .calibration import CalibrationEvidence
from .confidence import error_upper
from .errors import Refused
from .relation import Relation


@dataclass(frozen=True)
class MinimaxScore:
    relation: Relation
    worst_error: float


def select_minimax(admitted: tuple[CalibrationEvidence, ...]) -> tuple[MinimaxScore, ...]:
    if not admitted:
        raise Refused("NO_ADMITTED_RELATION")
    scores: list[MinimaxScore] = []
    for e in admitted:
        neg = e.false_positive + e.true_negative
        pos = e.false_negative + e.true_positive
        fpe = error_upper(e.false_positive, neg) if neg else 1.0
        fre = error_upper(e.false_negative, pos) if pos else 1.0
        scores.append(MinimaxScore(e.relation, max(fpe, fre)))
    best = min(s.worst_error for s in scores)
    return tuple(
        sorted((s for s in scores if s.worst_error == best), key=lambda s: s.relation.value)
    )
