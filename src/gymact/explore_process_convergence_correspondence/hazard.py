from dataclasses import dataclass
from fractions import Fraction
from .trajectory import Trajectory

@dataclass(frozen=True)
class Hazard:
    discharge: Fraction
    regression: Fraction

def transition_hazard(trajectory: Trajectory) -> Hazard:
    discharge = regression = count = 0
    for before, after in zip(trajectory.epochs, trajectory.epochs[1:]):
        old = {o.key: o.state for o in before.obligations}
        new = {o.key: o.state for o in after.obligations}
        for key in old:
            count += 1
            if new[key] < old[key]:
                discharge += 1
            elif new[key] > old[key]:
                regression += 1
    return Hazard(Fraction(discharge, count), Fraction(regression, count))
