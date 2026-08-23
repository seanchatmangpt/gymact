from __future__ import annotations

from fractions import Fraction

from .primal import PrimalPlan
from .refusal import refuse


def assert_mass_balance(
    plan: PrimalPlan,
    supply: dict[str, Fraction],
    demand: dict[str, Fraction],
) -> None:
    sent = {key: Fraction(0) for key in supply}
    received = {key: Fraction(0) for key in demand}
    for source, target, mass in plan.flows:
        if source not in sent or target not in received:
            refuse("PLAN_SUPPORT_MISMATCH", f"unknown edge {source}->{target}")
        sent[source] += mass
        received[target] += mass
    if sent != supply or received != demand:
        refuse("MASS_BALANCE", f"sent={sent} received={received}")
