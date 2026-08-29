from __future__ import annotations

from fractions import Fraction

from gymact.explore_kantorovich_duality.measure import FiniteMeasure
from gymact.explore_kantorovich_duality.metric import GroundMetric
from gymact.explore_kantorovich_duality.plan import TransportPlan
from gymact.explore_kantorovich_duality.potential import DualPotential

from .component_offsets import solve_component_offsets
from .raw_feasibility import verify_dual_feasibility
from .raw_marginals import verify_marginals
from .tight_components import derive_tight_components


def construct_dual(plan: TransportPlan, source: FiniteMeasure, target: FiniteMeasure, metric: GroundMetric) -> DualPotential:
    """Recover a deterministic feasible dual from complementary tight-edge equations.

    If the supplied feasible plan is not optimal, the induced difference-constraint
    system is unsatisfiable and fails closed instead of inventing a certificate.
    """
    verify_marginals(plan, source, target)
    components = derive_tight_components(plan, set(source.support), set(target.support), metric)
    offsets = solve_component_offsets(components, source, target, metric)
    u = {x: components.base_u[x] + offsets[components.source_component[x]] for x in source.support}
    v = {y: components.base_v[y] - offsets[components.target_component[y]] for y in target.support}
    if u:
        anchor = min(u)
        gauge = u[anchor]
        u = {x: value - gauge for x, value in u.items()}
        v = {y: value + gauge for y, value in v.items()}
    potential = DualPotential(u=u, v=v)
    verify_dual_feasibility(potential, source, target, metric)
    return potential
