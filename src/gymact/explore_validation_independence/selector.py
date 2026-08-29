from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction

from .composition import CompositionMode


class Strategy(StrEnum):
    MAX_COVERAGE = "MAX_COVERAGE"
    MIN_WIDTH = "MIN_WIDTH"
    MIN_OVERLAP = "MIN_OVERLAP"
    MINIMAX_MISS = "MINIMAX_MISS"


@dataclass(frozen=True)
class Candidate:
    mode: CompositionMode
    coverage: Fraction
    width: Fraction
    overlap: Fraction
    miss: Fraction
    cost: int


def select(candidates: tuple[Candidate, ...], strategy: Strategy) -> Candidate:
    if not candidates:
        raise ValueError("candidates required")
    key = {
        Strategy.MAX_COVERAGE: lambda c: (-c.coverage, c.width, c.overlap, c.cost),
        Strategy.MIN_WIDTH: lambda c: (c.width, -c.coverage, c.overlap, c.cost),
        Strategy.MIN_OVERLAP: lambda c: (c.overlap, -c.coverage, c.width, c.cost),
        Strategy.MINIMAX_MISS: lambda c: (c.miss, c.overlap, c.width, c.cost),
    }[strategy]
    return sorted(candidates, key=key)[0]
