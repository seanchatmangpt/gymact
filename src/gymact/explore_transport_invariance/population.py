from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from .refusal import require


@dataclass(frozen=True, slots=True)
class Cell:
    name: str
    source_mass: Fraction
    target_mass: Fraction

    def __post_init__(self) -> None:
        require(bool(self.name), "INVALID_CELL", "cell name is required")
        require(
            self.source_mass >= 0 and self.target_mass >= 0,
            "INVALID_MASS",
            "mass must be nonnegative",
        )


def normalize(cells: tuple[Cell, ...]) -> tuple[Cell, ...]:
    require(bool(cells), "EMPTY_POPULATION", "at least one cell is required")
    source_total = sum((c.source_mass for c in cells), Fraction())
    target_total = sum((c.target_mass for c in cells), Fraction())
    require(
        source_total > 0 and target_total > 0,
        "ZERO_POPULATION",
        "source and target totals must be positive",
    )
    return tuple(
        Cell(c.name, c.source_mass / source_total, c.target_mass / target_total) for c in cells
    )
