from __future__ import annotations

from fractions import Fraction

from .metric import GroundMetric
from .potential import DualPotential


def reduced_costs(potential: DualPotential, metric: GroundMetric, source: set[str], target: set[str]) -> dict[tuple[str, str], Fraction]:
    return {(x, y): metric(x, y) - potential.u[x] - potential.v[y] for x in source for y in target}
