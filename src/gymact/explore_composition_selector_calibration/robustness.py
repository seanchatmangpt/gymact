from dataclasses import dataclass
from fractions import Fraction

from .interval import Interval


@dataclass(frozen=True)
class Sensitivity:
    endpoint_shift: Fraction
    width_shift: Fraction


def compare_assumptions(conservative: Interval, independent: Interval) -> Sensitivity:
    endpoint = max(
        abs(conservative.lower - independent.lower),
        abs(conservative.upper - independent.upper),
    )
    return Sensitivity(endpoint, abs(conservative.width - independent.width))
