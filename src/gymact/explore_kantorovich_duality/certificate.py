from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from .complementarity import admit_complementary_slackness
from .dual import dual_value
from .measure import FiniteMeasure
from .metric import GroundMetric
from .plan import TransportPlan
from .potential import DualPotential
from .primal import primal_cost
from .refusal import DualityRefusal


@dataclass(frozen=True)
class DualityCertificate:
    primal: Fraction
    dual: Fraction

    @property
    def gap(self) -> Fraction:
        return self.primal - self.dual


def certify(plan: TransportPlan, potential: DualPotential, source: FiniteMeasure, target: FiniteMeasure, metric: GroundMetric) -> DualityCertificate:
    plan.admit(source, target)
    potential.admit(set(source.support), set(target.support), metric)
    admit_complementary_slackness(plan, potential, metric)
    p = primal_cost(plan, metric)
    d = dual_value(potential, source, target)
    if p != d:
        raise DualityRefusal("STRONG_DUALITY_GAP", f"{p}!={d}")
    return DualityCertificate(p, d)
