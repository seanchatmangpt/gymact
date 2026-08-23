from dataclasses import dataclass
from .trajectory import Trajectory

@dataclass(frozen=True)
class FixedPointWitness:
    stable: bool
    dwell: int
    digest: tuple[tuple[str, int], ...]

def detect(trajectory: Trajectory, required_dwell: int = 2) -> FixedPointWitness:
    states = [tuple((o.key, int(o.state)) for o in epoch.obligations) for epoch in trajectory.epochs]
    last = states[-1]
    dwell = 0
    for state in reversed(states):
        if state == last:
            dwell += 1
        else:
            break
    return FixedPointWitness(dwell >= required_dwell, dwell, last)
