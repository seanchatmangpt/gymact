from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction


@dataclass(frozen=True)
class IndependentWitness:
    engine: str
    primal: Fraction
    dual: Fraction
    gap: Fraction
    max_slack: Fraction
    active_arcs: int

    @property
    def optimal(self) -> bool:
        return self.gap == 0
