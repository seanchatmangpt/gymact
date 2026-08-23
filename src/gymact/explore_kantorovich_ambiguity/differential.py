from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from .ground import GroundMetric
from .kantorovich import wasserstein1
from .measure import FiniteMeasure
from .oracle import exhaustive_transport

@dataclass(frozen=True)
class Differential:
    primary: Fraction
    oracle: Fraction
    gap: Fraction

def compare(a: FiniteMeasure, b: FiniteMeasure, metric: GroundMetric, *, max_units: int = 64) -> Differential:
    primary = wasserstein1(a, b, metric).cost
    oracle = exhaustive_transport(a, b, metric, max_units=max_units).cost
    return Differential(primary, oracle, abs(primary - oracle))
