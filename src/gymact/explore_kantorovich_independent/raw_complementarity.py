from __future__ import annotations

from gymact.explore_kantorovich_duality.measure import FiniteMeasure
from gymact.explore_kantorovich_duality.metric import GroundMetric
from gymact.explore_kantorovich_duality.plan import TransportPlan
from gymact.explore_kantorovich_duality.potential import DualPotential

from .raw_reduced_cost import reduced_costs
from .refusal import IndependentVerifierRefusal


def verify_complementarity(plan: TransportPlan, potential: DualPotential, source: FiniteMeasure, target: FiniteMeasure, metric: GroundMetric) -> int:
    slack = reduced_costs(potential, source, target, metric)
    active = 0
    for edge, amount in plan.flow.items():
        if amount > 0:
            active += 1
            if slack[edge] != 0:
                raise IndependentVerifierRefusal("COMPLEMENTARITY_VIOLATION", f"{edge[0]}->{edge[1]}:{slack[edge]}")
    return active
