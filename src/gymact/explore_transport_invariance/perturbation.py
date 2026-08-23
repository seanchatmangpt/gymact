from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from .population import Cell
from .refusal import require


@dataclass(frozen=True, slots=True)
class Perturbation:
    cell: str
    source_delta: Fraction = Fraction()
    target_delta: Fraction = Fraction()


def apply(cells: tuple[Cell, ...], perturbations: tuple[Perturbation, ...]) -> tuple[Cell, ...]:
    by_name = {p.cell: p for p in perturbations}
    out = []
    for cell in cells:
        p = by_name.get(cell.name, Perturbation(cell.name))
        source = cell.source_mass + p.source_delta
        target = cell.target_mass + p.target_delta
        require(source >= 0 and target >= 0, "INVALID_PERTURBATION", cell.name)
        out.append(Cell(cell.name, source, target))
    return tuple(out)
