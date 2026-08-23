from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from .complementary_slackness import assert_complementary_slackness
from .dual_feasibility import assert_dual_feasible
from .mass_balance import assert_mass_balance
from .potentials import DualPotentials
from .primal import PrimalPlan
from .strong_duality import assert_strong_duality


@dataclass(frozen=True)
class DualityCertificate:
    optimum: Fraction
    edges: int
    positive_flows: int


def certify(plan: PrimalPlan, potentials: DualPotentials, metric: dict[tuple[str, str], Fraction], supply: dict[str, Fraction], demand: dict[str, Fraction]) -> DualityCertificate:
    assert_mass_balance(plan, supply, demand)
    assert_dual_feasible(potentials, metric)
    assert_complementary_slackness(plan, potentials, metric)
    optimum = assert_strong_duality(plan, potentials, metric, supply, demand)
    return DualityCertificate(optimum, len(metric), sum(1 for *_, mass in plan.flows if mass > 0))
