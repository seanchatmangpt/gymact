from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from .population import Cell
from .refusal import require


@dataclass(frozen=True, slots=True)
class Support:
    overlap: Fraction
    unsupported_target_mass: Fraction


def assess_support(cells: tuple[Cell, ...]) -> Support:
    unsupported = sum((c.target_mass for c in cells if c.target_mass > 0 and c.source_mass == 0), Fraction())
    overlap = sum((min(c.source_mass, c.target_mass) for c in cells), Fraction())
    require(unsupported == 0, "POSITIVITY_VIOLATION", f"unsupported target mass={unsupported}")
    return Support(overlap=overlap, unsupported_target_mass=unsupported)
