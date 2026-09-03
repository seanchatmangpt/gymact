from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from .selectors import SelectorKind


@dataclass(frozen=True, slots=True)
class StrategyVector:
    selector: SelectorKind
    coverage: Fraction
    ambiguity: Fraction
    freshness_lag: int

    def __post_init__(self) -> None:
        if (
            self.freshness_lag < 0
            or not (Fraction(0) <= self.coverage <= Fraction(1))
            or not (Fraction(0) <= self.ambiguity <= Fraction(1))
        ):
            raise ValueError("invalid strategy vector")


def _dominates(left: StrategyVector, right: StrategyVector) -> bool:
    weak = (
        left.coverage >= right.coverage
        and left.ambiguity <= right.ambiguity
        and left.freshness_lag <= right.freshness_lag
    )
    strict = (
        left.coverage > right.coverage
        or left.ambiguity < right.ambiguity
        or left.freshness_lag < right.freshness_lag
    )
    return weak and strict


def pareto_frontier(vectors: tuple[StrategyVector, ...]) -> tuple[StrategyVector, ...]:
    return tuple(
        vector
        for vector in vectors
        if not any(_dominates(other, vector) for other in vectors if other is not vector)
    )
