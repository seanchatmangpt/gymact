from __future__ import annotations

from fractions import Fraction

from gymact.explore_kantorovich_duality.measure import FiniteMeasure
from gymact.explore_kantorovich_duality.plan import TransportPlan

from .refusal import IndependentVerifierRefusal


def verify_marginals(plan: TransportPlan, source: FiniteMeasure, target: FiniteMeasure) -> None:
    if any(value < 0 for value in plan.flow.values()):
        raise IndependentVerifierRefusal("NEGATIVE_FLOW", "transport flow must be nonnegative")
    unknown_sources = {x for x, _ in plan.flow} - set(source.support)
    unknown_targets = {y for _, y in plan.flow} - set(target.support)
    if unknown_sources or unknown_targets:
        raise IndependentVerifierRefusal("FLOW_SUPPORT_MISMATCH", f"source={sorted(unknown_sources)},target={sorted(unknown_targets)}")
    for x, mass in source.mass.items():
        observed = sum((value for (i, _), value in plan.flow.items() if i == x), Fraction(0))
        if observed != mass:
            raise IndependentVerifierRefusal("SOURCE_MASS_MISMATCH", f"{x}:{observed}!={mass}")
    for y, mass in target.mass.items():
        observed = sum((value for (_, j), value in plan.flow.items() if j == y), Fraction(0))
        if observed != mass:
            raise IndependentVerifierRefusal("TARGET_MASS_MISMATCH", f"{y}:{observed}!={mass}")
