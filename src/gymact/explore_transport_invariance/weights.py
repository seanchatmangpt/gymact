from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from .population import Cell
from .refusal import require


@dataclass(frozen=True, slots=True)
class WeightSummary:
    weights: tuple[Fraction, ...]
    ess: Fraction
    max_weight: Fraction


def importance_weights(cells: tuple[Cell, ...], cap: Fraction | None = None) -> WeightSummary:
    values: list[Fraction] = []
    for cell in cells:
        require(cell.source_mass > 0 or cell.target_mass == 0, "POSITIVITY_VIOLATION", cell.name)
        raw = Fraction() if cell.target_mass == 0 else cell.target_mass / cell.source_mass
        values.append(min(raw, cap) if cap is not None else raw)
    total = sum(values, Fraction())
    sq = sum((w * w for w in values), Fraction())
    ess = Fraction() if sq == 0 else total * total / sq
    return WeightSummary(tuple(values), ess, max(values, default=Fraction()))
