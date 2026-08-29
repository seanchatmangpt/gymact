from __future__ import annotations

from fractions import Fraction

from gymact.explore_kantorovich_duality.measure import FiniteMeasure
from gymact.explore_kantorovich_duality.metric import GroundMetric
from gymact.explore_kantorovich_duality.potential import DualPotential

from .refusal import IndependentVerifierRefusal


def verify_dual_feasibility(potential: DualPotential, source: FiniteMeasure, target: FiniteMeasure, metric: GroundMetric) -> Fraction:
    if set(potential.u) != set(source.support) or set(potential.v) != set(target.support):
        raise IndependentVerifierRefusal("DUAL_SUPPORT_MISMATCH", "dual potentials must cover both supports exactly")
    max_slack = Fraction(0)
    for x in source.support:
        for y in target.support:
            slack = metric(x, y) - potential.u[x] - potential.v[y]
            if slack < 0:
                raise IndependentVerifierRefusal("DUAL_INFEASIBLE", f"{x}->{y}:{-slack}")
            max_slack = max(max_slack, slack)
    return max_slack
