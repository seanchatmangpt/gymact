from fractions import Fraction
from .epoch import ClosureEpoch
from .obligation import State

def weighted_l1(epoch: ClosureEpoch) -> Fraction:
    total = sum((o.weight for o in epoch.obligations), Fraction())
    debt = sum((o.weight * Fraction(int(o.state), int(State.FAIL)) for o in epoch.obligations), Fraction())
    return debt / total

def max_severity(epoch: ClosureEpoch) -> Fraction:
    if not epoch.obligations:
        return Fraction()
    return Fraction(max(int(o.state) for o in epoch.obligations), int(State.FAIL))

def lexicographic_vector(epoch: ClosureEpoch) -> tuple[int, ...]:
    return tuple(sum(1 for o in epoch.obligations if o.state == state) for state in reversed(tuple(State)))
