from __future__ import annotations

from dataclasses import replace
from fractions import Fraction

from .plan import TransportPlan
from .potential import DualPotential


def perturb_plan(plan: TransportPlan, edge: tuple[str, str], delta: Fraction) -> TransportPlan:
    flow = dict(plan.flow)
    flow[edge] = flow.get(edge, Fraction(0)) + delta
    return replace(plan, flow=flow)


def perturb_potential(potential: DualPotential, node: str, delta: Fraction) -> DualPotential:
    u = dict(potential.u)
    if node in u:
        u[node] += delta
        return replace(potential, u=u)
    v = dict(potential.v)
    v[node] += delta
    return replace(potential, v=v)
