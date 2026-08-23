from dataclasses import dataclass
from .trajectory import Trajectory
from .potential import weighted_l1

@dataclass(frozen=True)
class LyapunovWitness:
    nonincreasing: bool
    strict_steps: int
    violations: tuple[int, ...]

def witness(trajectory: Trajectory) -> LyapunovWitness:
    values = [weighted_l1(epoch) for epoch in trajectory.epochs]
    violations: list[int] = []
    strict = 0
    for index, (before, after) in enumerate(zip(values, values[1:]), 1):
        if after > before:
            violations.append(index)
        elif after < before:
            strict += 1
    return LyapunovWitness(not violations, strict, tuple(violations))
