from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from .certificate import certify
from .measure import FiniteMeasure
from .metric import GroundMetric
from .plan import TransportPlan
from .potential import DualPotential


@dataclass(frozen=True)
class CheckResult:
    primal: Fraction
    dual: Fraction
    gap: Fraction


def independent_check(plan: TransportPlan, potential: DualPotential, source: FiniteMeasure, target: FiniteMeasure, metric: GroundMetric) -> CheckResult:
    cert = certify(plan, potential, source, target, metric)
    return CheckResult(cert.primal, cert.dual, cert.gap)
