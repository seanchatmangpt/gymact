from __future__ import annotations

import itertools
from dataclasses import dataclass
from fractions import Fraction
from typing import Mapping

from .ambiguity import AmbiguitySet
from .measure import FiniteMeasure
from .refusal import Refused

@dataclass(frozen=True)
class WorstCase:
    value: Fraction
    witness: FiniteMeasure
    evaluated: int

def simplex_lattice(points: tuple[str, ...], denominator: int) -> tuple[FiniteMeasure, ...]:
    if denominator <= 0:
        raise Refused("INVALID_LATTICE_DENOMINATOR")
    if not points:
        raise Refused("EMPTY_LATTICE_SUPPORT")
    out = []
    for cuts in itertools.combinations(range(denominator + len(points) - 1), len(points) - 1):
        bars = (-1, *cuts, denominator + len(points) - 1)
        counts = tuple(bars[i + 1] - bars[i] - 1 for i in range(len(points)))
        out.append(FiniteMeasure.from_mapping(dict(zip(points, counts, strict=True))))
    return tuple(out)

def worst_case_lattice(
    ambiguity: AmbiguitySet,
    loss: Mapping[str, int | str | Fraction],
    *,
    denominator: int = 12,
) -> WorstCase:
    candidates = [
        c for c in simplex_lattice(ambiguity.center.support, denominator) if ambiguity.contains(c)
    ]
    if not candidates:
        raise Refused("EMPTY_ADMITTED_LATTICE")
    ranked = sorted((c.expectation(loss), c.digest_tuple(), c) for c in candidates)
    value, _, witness = ranked[-1]
    return WorstCase(value, witness, len(candidates))
