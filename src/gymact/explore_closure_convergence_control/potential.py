from __future__ import annotations

from fractions import Fraction

from .trajectory import ClosureEpoch


def closure_debt(epoch: ClosureEpoch) -> Fraction:
    total = sum((item.debt for item in epoch.obligations), start=Fraction(0))
    return total / len(epoch.obligations)


def closure_potential(epoch: ClosureEpoch) -> Fraction:
    return Fraction(1) - closure_debt(epoch)


def potential_delta(previous: ClosureEpoch, current: ClosureEpoch) -> Fraction:
    return closure_potential(current) - closure_potential(previous)
