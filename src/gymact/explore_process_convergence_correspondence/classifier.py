from enum import StrEnum
from .trajectory import Trajectory
from .oscillation import oscillating_keys
from .hazard import transition_hazard
from .discrete_calculus import velocity
from .lyapunov import witness

class Direction(StrEnum):
    CONVERGING = "CONVERGING"
    OSCILLATING = "OSCILLATING"
    REGRESSING = "REGRESSING"
    STALLED = "STALLED"
    UNKNOWN = "UNKNOWN"

class Strategy(StrEnum):
    POTENTIAL = "POTENTIAL"
    HAZARD = "HAZARD"
    LYAPUNOV = "LYAPUNOV"
    MINIMAX = "MINIMAX"

def classify(trajectory: Trajectory, strategy: Strategy) -> Direction:
    speeds = velocity(trajectory)
    hazard = transition_hazard(trajectory)
    if oscillating_keys(trajectory):
        return Direction.OSCILLATING
    if strategy == Strategy.POTENTIAL:
        if all(value < 0 for value in speeds):
            return Direction.CONVERGING
        if all(value == 0 for value in speeds):
            return Direction.STALLED
        if speeds[-1] > 0:
            return Direction.REGRESSING
    elif strategy == Strategy.HAZARD:
        if hazard.discharge > hazard.regression:
            return Direction.CONVERGING
        if hazard.regression > hazard.discharge:
            return Direction.REGRESSING
        return Direction.STALLED
    elif strategy == Strategy.LYAPUNOV:
        result = witness(trajectory)
        if result.nonincreasing and result.strict_steps:
            return Direction.CONVERGING
        return Direction.REGRESSING if result.violations else Direction.STALLED
    else:
        worst = max(speeds)
        if worst < 0:
            return Direction.CONVERGING
        return Direction.STALLED if worst == 0 else Direction.REGRESSING
    return Direction.UNKNOWN
