from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from .refusal import refuse


@dataclass(frozen=True)
class PrimalPlan:
    flows: tuple[tuple[str, str, Fraction], ...]

    def __post_init__(self) -> None:
        if not self.flows:
            refuse("EMPTY_PLAN", "at least one flow required")
        for source, target, mass in self.flows:
            if not source or not target or mass < 0:
                refuse("INVALID_PLAN", "flow endpoints and nonnegative mass required")

    def cost(self, metric: dict[tuple[str, str], Fraction]) -> Fraction:
        total = Fraction(0)
        for source, target, mass in self.flows:
            key = (source, target)
            if key not in metric:
                refuse("MISSING_GROUND_COST", f"missing cost {key}")
            total += mass * metric[key]
        return total
