from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction
from typing import Iterable

from .refusals import refuse


@dataclass(frozen=True, slots=True)
class Candidate:
    name: str
    nominal_risk: Fraction
    worst_risk: Fraction
    radius: Fraction
    support: Fraction


class Selector(StrEnum):
    MIN_NOMINAL = "MIN_NOMINAL"
    MIN_WORST = "MIN_WORST"
    MIN_RADIUS = "MIN_RADIUS"
    MAX_SUPPORT = "MAX_SUPPORT"


def select(candidates: Iterable[Candidate], selector: Selector) -> Candidate:
    items = tuple(candidates)
    if not items:
        raise refuse("EMPTY_CANDIDATES", "selector requires candidates")
    keys = {
        Selector.MIN_NOMINAL: lambda c: (c.nominal_risk, c.name),
        Selector.MIN_WORST: lambda c: (c.worst_risk, c.name),
        Selector.MIN_RADIUS: lambda c: (c.radius, c.name),
        Selector.MAX_SUPPORT: lambda c: (-c.support, c.name),
    }
    return min(items, key=keys[selector])
