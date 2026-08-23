from __future__ import annotations

from fractions import Fraction

from .metric import GroundMetric
from .plan import TransportPlan


def primal_cost(plan: TransportPlan, metric: GroundMetric) -> Fraction:
    return sum((mass * metric(i, j) for (i, j), mass in plan.flow.items()), Fraction(0))
