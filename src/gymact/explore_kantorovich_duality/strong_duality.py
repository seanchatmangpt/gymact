from __future__ import annotations

from fractions import Fraction

from .potentials import DualPotentials
from .primal import PrimalPlan
from .refusal import refuse


def assert_strong_duality(
    plan: PrimalPlan,
    potentials: DualPotentials,
    metric: dict[tuple[str, str], Fraction],
    supply: dict[str, Fraction],
    demand: dict[str, Fraction],
) -> Fraction:
    primal = plan.cost(metric)
    dual = potentials.objective(supply, demand)
    if primal != dual:
        refuse("DUALITY_GAP", f"primal={primal} dual={dual}")
    return primal
