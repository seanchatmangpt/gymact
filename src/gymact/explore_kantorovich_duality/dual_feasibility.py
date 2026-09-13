from __future__ import annotations

from fractions import Fraction

from .potentials import DualPotentials
from .refusal import refuse


def assert_dual_feasible(
    potentials: DualPotentials,
    metric: dict[tuple[str, str], Fraction],
) -> None:
    for (source, target), ground in metric.items():
        if potentials.reduced_cost(source, target, ground) < 0:
            refuse("DUAL_INFEASIBLE", f"negative reduced cost for {source}->{target}")
