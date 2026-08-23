from __future__ import annotations

from fractions import Fraction

from gymact.explore_kantorovich_duality.measure import FiniteMeasure
from gymact.explore_kantorovich_duality.metric import GroundMetric
from gymact.explore_kantorovich_duality.potential import DualPotential


def reduced_costs(potential: DualPotential, source: FiniteMeasure, target: FiniteMeasure, metric: GroundMetric) -> dict[tuple[str, str], Fraction]:
    return {(x, y): metric(x, y) - potential.u[x] - potential.v[y] for x in source.support for y in target.support}
