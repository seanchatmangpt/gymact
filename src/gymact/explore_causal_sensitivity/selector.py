from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction

from .manski import Interval


class Selector(StrEnum):
    MAX_LOWER = "MAX_LOWER"
    MIN_WIDTH = "MIN_WIDTH"
    MAX_MIDPOINT = "MAX_MIDPOINT"


@dataclass(frozen=True)
class NamedInterval:
    name: str
    interval: Interval


def select(items: tuple[NamedInterval, ...], strategy: Selector) -> NamedInterval:
    if not items:
        raise ValueError("no candidates")
    if strategy is Selector.MAX_LOWER:
        return max(items, key=lambda x: (x.interval.lower, x.name))
    if strategy is Selector.MIN_WIDTH:
        return min(items, key=lambda x: (x.interval.width(), x.name))
    return max(
        items,
        key=lambda x: ((x.interval.lower + x.interval.upper) / Fraction(2), x.name),
    )
