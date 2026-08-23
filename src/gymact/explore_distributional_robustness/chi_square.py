from __future__ import annotations

from fractions import Fraction

from .distribution import FiniteDistribution
from .refusals import refuse


def chi_square(candidate: FiniteDistribution, center: FiniteDistribution) -> Fraction:
    p = candidate.as_dict()
    q = center.as_dict()
    if not p.keys() <= q.keys():
        raise refuse("POSITIVITY_VIOLATION", "candidate support exceeds center support")
    total = Fraction(0)
    for key in q:
        if q[key] == 0 and p.get(key, 0) != 0:
            raise refuse("POSITIVITY_VIOLATION", f"zero center mass at {key}")
        if q[key] > 0:
            delta = p.get(key, Fraction(0)) - q[key]
            total += delta * delta / q[key]
    return total
