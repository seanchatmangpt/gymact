from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from .state import ObligationState, WEIGHT
from .trajectory import ClosureEpoch


@dataclass(frozen=True, slots=True)
class Hazard:
    discharge: Fraction
    regression: Fraction


def transition_hazard(epochs: tuple[ClosureEpoch, ...]) -> Hazard:
    discharge = 0
    regression = 0
    transitions = 0
    for previous, current in zip(epochs, epochs[1:], strict=True):
        old = {item.key: item.state for item in previous.obligations}
        for item in current.obligations:
            transitions += 1
            before = old[item.key]
            if WEIGHT[item.state] < WEIGHT[before]:
                discharge += 1
            elif WEIGHT[item.state] > WEIGHT[before]:
                regression += 1
    if transitions == 0:
        return Hazard(Fraction(0), Fraction(0))
    return Hazard(Fraction(discharge, transitions), Fraction(regression, transitions))
