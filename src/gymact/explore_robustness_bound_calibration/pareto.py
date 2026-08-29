from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction


@dataclass(frozen=True, slots=True)
class CandidateVector:
    name: str
    coverage: Fraction
    identification_value: Fraction
    mean_width: Fraction


def dominates(a: CandidateVector, b: CandidateVector) -> bool:
    not_worse = (
        a.coverage >= b.coverage
        and a.identification_value >= b.identification_value
        and a.mean_width <= b.mean_width
    )
    strictly = (
        a.coverage > b.coverage
        or a.identification_value > b.identification_value
        or a.mean_width < b.mean_width
    )
    return not_worse and strictly


def frontier(candidates: tuple[CandidateVector, ...]) -> tuple[CandidateVector, ...]:
    return tuple(
        candidate
        for candidate in candidates
        if not any(dominates(other, candidate) for other in candidates if other is not candidate)
    )
