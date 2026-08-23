from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from .measure import FiniteMeasure
from .refusal import DualityRefusal


@dataclass(frozen=True)
class TransportPlan:
    flow: dict[tuple[str, str], Fraction]

    def admit(self, source: FiniteMeasure, target: FiniteMeasure) -> "TransportPlan":
        if any(v < 0 for v in self.flow.values()):
            raise DualityRefusal("NEGATIVE_FLOW", "transport flow must be nonnegative")
        for x, mass in source.mass.items():
            row = sum((v for (i, _), v in self.flow.items() if i == x), Fraction(0))
            if row != mass:
                raise DualityRefusal("SOURCE_MASS_MISMATCH", f"{x}:{row}!={mass}")
        for y, mass in target.mass.items():
            col = sum((v for (_, j), v in self.flow.items() if j == y), Fraction(0))
            if col != mass:
                raise DualityRefusal("TARGET_MASS_MISMATCH", f"{y}:{col}!={mass}")
        return self
