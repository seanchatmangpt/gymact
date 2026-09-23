from fractions import Fraction
from itertools import pairwise

from .potential import weighted_l1
from .trajectory import Trajectory


def velocity(trajectory: Trajectory) -> tuple[Fraction, ...]:
    potential = [weighted_l1(epoch) for epoch in trajectory.epochs]
    return tuple(after - before for before, after in pairwise(potential))


def acceleration(trajectory: Trajectory) -> tuple[Fraction, ...]:
    speeds = velocity(trajectory)
    return tuple(after - before for before, after in pairwise(speeds))
