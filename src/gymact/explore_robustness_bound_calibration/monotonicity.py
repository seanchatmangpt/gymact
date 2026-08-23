from __future__ import annotations

from .bound import RobustnessBound
from .refusal import Refused, REFUSED_NON_MONOTONE_ENVELOPE


def require_monotone(bounds: tuple[RobustnessBound, ...]) -> tuple[RobustnessBound, ...]:
    ordered = tuple(sorted(bounds, key=lambda b: b.gamma))
    for previous, current in zip(ordered, ordered[1:]):
        if current.lower > previous.lower or current.upper < previous.upper:
            raise Refused(REFUSED_NON_MONOTONE_ENVELOPE, f"gamma {previous.gamma}->{current.gamma}")
    return ordered
