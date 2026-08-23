from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from .refusal import refuse


@dataclass(frozen=True)
class DualPotentials:
    source: dict[str, Fraction]
    target: dict[str, Fraction]

    def reduced_cost(self, s: str, t: str, ground: Fraction) -> Fraction:
        if s not in self.source or t not in self.target:
            refuse("MISSING_POTENTIAL", f"missing potential for {s}->{t}")
        return ground - self.source[s] - self.target[t]

    def objective(self, supply: dict[str, Fraction], demand: dict[str, Fraction]) -> Fraction:
        if set(supply) != set(self.source) or set(demand) != set(self.target):
            refuse("POTENTIAL_SUPPORT_MISMATCH", "dual support must equal measure support")
        return sum((supply[k] * self.source[k] for k in supply), Fraction(0)) + sum(
            (demand[k] * self.target[k] for k in demand), Fraction(0)
        )
