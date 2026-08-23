from __future__ import annotations

from fractions import Fraction
from typing import Mapping

from .distribution import FiniteDistribution
from .refusals import refuse


def wasserstein_1(
    left: FiniteDistribution,
    right: FiniteDistribution,
    ground_cost: Mapping[tuple[str, str], Fraction | int],
) -> Fraction:
    if left.support != right.support:
        raise refuse("UNSUPPORTED_WASSERSTEIN_SUPPORT", "bounded exact solver requires shared ordered support")
    keys = sorted(left.support)
    if len(keys) != 2:
        raise refuse("UNSUPPORTED_WASSERSTEIN_DIMENSION", "exact bounded solver currently admits two-point support")
    a, b = keys
    cost = Fraction(ground_cost.get((a, b), ground_cost.get((b, a), -1)))
    if cost < 0:
        raise refuse("MISSING_GROUND_COST", f"missing nonnegative cost for {a}<->{b}")
    delta = abs(left.as_dict()[a] - right.as_dict()[a])
    return delta * cost
