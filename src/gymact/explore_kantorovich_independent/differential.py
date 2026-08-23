from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from gymact.explore_kantorovich_duality.certificate import certify
from gymact.explore_kantorovich_duality.measure import FiniteMeasure
from gymact.explore_kantorovich_duality.metric import GroundMetric
from gymact.explore_kantorovich_duality.plan import TransportPlan
from gymact.explore_kantorovich_duality.potential import DualPotential

from .engine_identity import INDEPENDENT_ENGINE, MANUFACTURER_ENGINE, admit_independent
from .raw_verifier import verify
from .refusal import IndependentVerifierRefusal


@dataclass(frozen=True)
class DifferentialResult:
    manufacturer_primal: Fraction
    manufacturer_dual: Fraction
    independent_primal: Fraction
    independent_dual: Fraction


def compare(plan: TransportPlan, potential: DualPotential, source: FiniteMeasure, target: FiniteMeasure, metric: GroundMetric) -> DifferentialResult:
    admit_independent(INDEPENDENT_ENGINE, MANUFACTURER_ENGINE)
    manufactured = certify(plan, potential, source, target, metric)
    independent = verify(plan, potential, source, target, metric)
    if (manufactured.primal, manufactured.dual) != (independent.primal, independent.dual):
        raise IndependentVerifierRefusal("VERIFIER_DIVERGENCE", f"manufacturer={manufactured.primal}/{manufactured.dual},independent={independent.primal}/{independent.dual}")
    return DifferentialResult(manufactured.primal, manufactured.dual, independent.primal, independent.dual)
