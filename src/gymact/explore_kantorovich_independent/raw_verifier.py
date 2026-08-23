from __future__ import annotations

from gymact.explore_kantorovich_duality.measure import FiniteMeasure
from gymact.explore_kantorovich_duality.metric import GroundMetric
from gymact.explore_kantorovich_duality.plan import TransportPlan
from gymact.explore_kantorovich_duality.potential import DualPotential

from .raw_complementarity import verify_complementarity
from .raw_dual import dual_value
from .raw_feasibility import verify_dual_feasibility
from .raw_marginals import verify_marginals
from .raw_primal import primal_value
from .refusal import IndependentVerifierRefusal
from .witness import IndependentWitness

ENGINE_ID = "gymact.kantorovich.independent-equation-verifier/v1"


def verify(plan: TransportPlan, potential: DualPotential, source: FiniteMeasure, target: FiniteMeasure, metric: GroundMetric) -> IndependentWitness:
    verify_marginals(plan, source, target)
    max_slack = verify_dual_feasibility(potential, source, target, metric)
    active = verify_complementarity(plan, potential, source, target, metric)
    primal = primal_value(plan, metric)
    dual = dual_value(potential, source, target)
    gap = primal - dual
    if gap != 0:
        raise IndependentVerifierRefusal("STRONG_DUALITY_GAP", f"{primal}!={dual}")
    return IndependentWitness(ENGINE_ID, primal, dual, gap, max_slack, active)
