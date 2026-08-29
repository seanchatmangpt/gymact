from .trajectory import Trajectory
from .obligation import State

def stable_dwell(trajectory: Trajectory, target: State = State.PASS) -> int:
    count = 0
    for epoch in reversed(trajectory.epochs):
        if all(o.state == target for o in epoch.obligations):
            count += 1
        else:
            break
    return count
