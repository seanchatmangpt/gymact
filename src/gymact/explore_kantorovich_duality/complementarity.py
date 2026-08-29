from __future__ import annotations

from .metric import GroundMetric
from .plan import TransportPlan
from .potential import DualPotential
from .refusal import DualityRefusal


def admit_complementary_slackness(plan: TransportPlan, potential: DualPotential, metric: GroundMetric) -> None:
    for edge, mass in plan.flow.items():
        if mass > 0:
            x, y = edge
            if potential.u[x] + potential.v[y] != metric(x, y):
                raise DualityRefusal("COMPLEMENTARY_SLACKNESS_VIOLATION", f"{x}->{y}")
