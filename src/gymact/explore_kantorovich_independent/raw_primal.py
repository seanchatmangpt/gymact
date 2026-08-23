from __future__ import annotations

from fractions import Fraction

from gymact.explore_kantorovich_duality.metric import GroundMetric
from gymact.explore_kantorovich_duality.plan import TransportPlan


def primal_value(plan: TransportPlan, metric: GroundMetric) -> Fraction:
    return sum((amount * metric(x, y) for (x, y), amount in plan.flow.items()), Fraction(0))
