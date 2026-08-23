from dataclasses import dataclass
from fractions import Fraction
from .classifier import Strategy, Direction, classify
from .trajectory import Trajectory
from .hazard import transition_hazard
from .oscillation import oscillating_keys
from .potential import weighted_l1

@dataclass(frozen=True)
class Candidate:
    strategy: Strategy
    debt: Fraction
    regress: Fraction
    oscillations: int
    direction: Direction

def candidates(trajectory: Trajectory) -> tuple[Candidate, ...]:
    hazard = transition_hazard(trajectory)
    debt = weighted_l1(trajectory.epochs[-1])
    oscillations = len(oscillating_keys(trajectory))
    return tuple(Candidate(strategy, debt, hazard.regression, oscillations, classify(trajectory, strategy)) for strategy in Strategy)

def frontier(items: tuple[Candidate, ...]) -> tuple[Candidate, ...]:
    def dominates(a: Candidate, b: Candidate) -> bool:
        weak = a.debt <= b.debt and a.regress <= b.regress and a.oscillations <= b.oscillations
        strict = a.debt < b.debt or a.regress < b.regress or a.oscillations < b.oscillations
        return weak and strict
    return tuple(item for item in items if not any(dominates(other, item) for other in items if other != item))
