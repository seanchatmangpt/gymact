from __future__ import annotations

from fractions import Fraction

from .distribution import FiniteDistribution
from .refusals import refuse


def two_point_extremes(center: FiniteDistribution, radius: Fraction) -> tuple[FiniteDistribution, ...]:
    if radius < 0 or radius > 1:
        raise refuse("INVALID_RADIUS", "two-point TV radius must be in [0,1]")
    if len(center.mass) != 2:
        raise refuse("UNSUPPORTED_ADVERSARY_DIMENSION", "bounded adversary currently requires two-point support")
    (a, pa), (b, pb) = center.mass
    shift = min(radius, pa, pb)
    low = FiniteDistribution.from_mapping({a: pa - shift, b: pb + shift})
    high = FiniteDistribution.from_mapping({a: pa + shift, b: pb - shift})
    return tuple(dict.fromkeys((center, low, high)))
