from __future__ import annotations

from dataclasses import dataclass

from .calibration import CalibrationEvidence
from .relation import Relation


@dataclass(frozen=True)
class Candidate:
    relation: Relation
    false_equivalence: float
    false_refusal: float
    cost_micros: int


def frontier(admitted: tuple[CalibrationEvidence, ...]) -> tuple[Candidate, ...]:
    candidates = tuple(Candidate(e.relation, e.false_equivalence_rate, e.false_refusal_rate, e.cost_micros) for e in admitted)
    def dominates(a: Candidate, b: Candidate) -> bool:
        av = (a.false_equivalence, a.false_refusal, a.cost_micros)
        bv = (b.false_equivalence, b.false_refusal, b.cost_micros)
        return all(x <= y for x, y in zip(av, bv)) and any(x < y for x, y in zip(av, bv))
    return tuple(sorted((c for c in candidates if not any(dominates(o, c) for o in candidates if o != c)), key=lambda c: c.relation.value))
