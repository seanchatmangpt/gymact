from fractions import Fraction
from .trajectory import Trajectory
from .potential import weighted_l1

def velocity(trajectory: Trajectory) -> tuple[Fraction, ...]:
    potential = [weighted_l1(epoch) for epoch in trajectory.epochs]
    return tuple(after - before for before, after in zip(potential, potential[1:]))

def acceleration(trajectory: Trajectory) -> tuple[Fraction, ...]:
    speeds = velocity(trajectory)
    return tuple(after - before for before, after in zip(speeds, speeds[1:]))
