from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from .ambiguity import AmbiguitySet
from .measure import FiniteMeasure
from .refusal import Refused

@dataclass(frozen=True)
class Membership:
    admitted: bool
    distances: tuple[tuple[str, Fraction], ...]

def intersect(candidate: FiniteMeasure, sets: tuple[AmbiguitySet, ...]) -> Membership:
    if not sets:
        raise Refused("EMPTY_AMBIGUITY_INTERSECTION")
    distances = tuple((s.kind.value, s.distance(candidate)) for s in sets)
    return Membership(all(d <= s.radius for (_, d), s in zip(distances, sets, strict=True)), distances)
