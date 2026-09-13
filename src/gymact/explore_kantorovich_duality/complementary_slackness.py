from __future__ import annotations

from fractions import Fraction

from .potentials import DualPotentials
from .primal import PrimalPlan
from .refusal import refuse


def assert_complementary_slackness(
    plan: PrimalPlan,
    potentials: DualPotentials,
    metric: dict[tuple[str, str], Fraction],
) -> None:
    for source, target, mass in plan.flows:
        if mass == 0:
            continue
        reduced = potentials.reduced_cost(source, target, metric[(source, target)])
        if reduced != 0:
            refuse("COMPLEMENTARY_SLACKNESS", f"positive flow has reduced cost {reduced}")
