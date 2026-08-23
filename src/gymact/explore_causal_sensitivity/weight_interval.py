from dataclasses import dataclass
from fractions import Fraction

from .gamma import Gamma


@dataclass(frozen=True)
class WeightInterval:
    lower: Fraction
    upper: Fraction


def weight_interval(target: Fraction, behavior: Fraction, gamma: Gamma) -> WeightInterval:
    if not 0 <= target <= 1 or not 0 < behavior < 1:
        raise ValueError("invalid propensity")
    low_b, high_b = gamma.odds_ratio_bounds(behavior)
    if target == 0:
        return WeightInterval(Fraction(0), Fraction(0))
    return WeightInterval(target / high_b, target / low_b)
