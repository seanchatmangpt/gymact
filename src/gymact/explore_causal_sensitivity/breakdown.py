from dataclasses import dataclass
from fractions import Fraction
from typing import Callable

from .gamma import Gamma
from .manski import Interval


@dataclass(frozen=True)
class Breakdown:
    gamma: Fraction
    interval: Interval


def first_crossing(evaluate: Callable[[Gamma], Interval], threshold: Fraction, grid: tuple[Fraction, ...]) -> Breakdown | None:
    for value in sorted(set(grid)):
        interval = evaluate(Gamma(value))
        if interval.lower <= threshold <= interval.upper:
            return Breakdown(value, interval)
    return None
