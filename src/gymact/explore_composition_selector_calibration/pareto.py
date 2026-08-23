from dataclasses import dataclass
from fractions import Fraction

@dataclass(frozen=True)
class Candidate:
    name: str
    coverage: Fraction
    width: Fraction
    sensitivity: Fraction
    cost: Fraction


def dominates(a: Candidate, b: Candidate) -> bool:
    weak = a.coverage >= b.coverage and a.width <= b.width and a.sensitivity <= b.sensitivity and a.cost <= b.cost
    strict = a.coverage > b.coverage or a.width < b.width or a.sensitivity < b.sensitivity or a.cost < b.cost
    return weak and strict


def frontier(candidates: tuple[Candidate, ...]) -> tuple[Candidate, ...]:
    return tuple(c for c in candidates if not any(dominates(other, c) for other in candidates if other != c))
