from __future__ import annotations

from fractions import Fraction

from .potentials import DualPotentials
from .primal import PrimalPlan
from .refusal import refuse


def independent_gap(plan: PrimalPlan, potentials: DualPotentials, metric: dict[tuple[str, str], Fraction], supply: dict[str, Fraction], demand: dict[str, Fraction]) -> Fraction:
    primal = sum((mass * metric[(s, t)] for s, t, mass in plan.flows), Fraction(0))
    dual = sum((supply[k] * potentials.source[k] for k in sorted(supply)), Fraction(0)) + sum((demand[k] * potentials.target[k] for k in sorted(demand)), Fraction(0))
    gap = primal - dual
    if gap < 0:
        refuse("WEAK_DUALITY_VIOLATION", f"dual exceeds primal by {-gap}")
    return gap
