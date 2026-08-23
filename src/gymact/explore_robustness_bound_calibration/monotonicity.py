from __future__ import annotations

from itertools import pairwise

from .bound import RobustnessBound
from .refusal import REFUSED_NON_MONOTONE_ENVELOPE, Refused


def require_monotone(bounds: tuple[RobustnessBound, ...]) -> tuple[RobustnessBound, ...]:
    ordered = tuple(sorted(bounds, key=lambda bound: bound.gamma))
    for previous, current in pairwise(ordered):
        if current.lower > previous.lower or current.upper < previous.upper:
            raise Refused(
                REFUSED_NON_MONOTONE_ENVELOPE,
                f"gamma {previous.gamma}->{current.gamma}",
            )
    return ordered
