from __future__ import annotations

import math

from .distribution import ErrorDistribution


def _kl(p: tuple[float, ...], q: tuple[float, ...]) -> float:
    return sum(a * math.log2(a / b) for a, b in zip(p, q) if a > 0)


def jensen_shannon(left: ErrorDistribution, right: ErrorDistribution) -> float:
    p = tuple(float(v) for v in left.as_tuple())
    q = tuple(float(v) for v in right.as_tuple())
    midpoint = tuple((a + b) / 2 for a, b in zip(p, q))
    return (_kl(p, midpoint) + _kl(q, midpoint)) / 2
