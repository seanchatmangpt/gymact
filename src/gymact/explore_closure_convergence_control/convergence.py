from __future__ import annotations

from enum import StrEnum
from fractions import Fraction

from .hazard import transition_hazard
from .oscillation import oscillating_obligations
from .potential import potential_delta
from .trajectory import ClosureEpoch


class Direction(StrEnum):
    CONVERGING = "CONVERGING"
    OSCILLATING = "OSCILLATING"
    REGRESSING = "REGRESSING"
    STALLED = "STALLED"
    UNKNOWN = "UNKNOWN"


def classify(epochs: tuple[ClosureEpoch, ...]) -> Direction:
    if len(epochs) < 2:
        return Direction.UNKNOWN
    if oscillating_obligations(epochs):
        return Direction.OSCILLATING
    hazard = transition_hazard(epochs)
    delta = potential_delta(epochs[-2], epochs[-1])
    if delta > 0 and hazard.discharge >= hazard.regression:
        return Direction.CONVERGING
    if delta < 0 or hazard.regression > hazard.discharge:
        return Direction.REGRESSING
    if delta == Fraction(0):
        return Direction.STALLED
    return Direction.UNKNOWN
