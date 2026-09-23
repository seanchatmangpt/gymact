from itertools import pairwise

from .trajectory import Trajectory


def oscillating_keys(trajectory: Trajectory) -> tuple[str, ...]:
    output: list[str] = []
    for key in trajectory.epochs[0].universe:
        states = [
            next(o.state for o in epoch.obligations if o.key == key) for epoch in trajectory.epochs
        ]
        changes = sum(a != b for a, b in pairwise(states))
        if changes >= 2 and states[0] == states[-1]:
            output.append(key)
    return tuple(output)
