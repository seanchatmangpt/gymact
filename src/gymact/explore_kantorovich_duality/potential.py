from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from .metric import GroundMetric
from .refusal import DualityRefusal


@dataclass(frozen=True)
class DualPotential:
    u: dict[str, Fraction]
    v: dict[str, Fraction]

    def admit(self, source_support: set[str], target_support: set[str], metric: GroundMetric) -> "DualPotential":
        if set(self.u) != source_support or set(self.v) != target_support:
            raise DualityRefusal("DUAL_SUPPORT_MISMATCH", "dual potentials must cover both supports exactly")
        for x in source_support:
            for y in target_support:
                if self.u[x] + self.v[y] > metric(x, y):
                    raise DualityRefusal("DUAL_INFEASIBLE", f"{x}->{y}")
        return self
