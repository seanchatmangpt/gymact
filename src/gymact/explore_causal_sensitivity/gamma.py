from dataclasses import dataclass
from fractions import Fraction


@dataclass(frozen=True)
class Gamma:
    value: Fraction

    def __post_init__(self) -> None:
        if self.value < 1:
            raise ValueError("gamma must be >= 1")

    def odds_ratio_bounds(self, propensity: Fraction) -> tuple[Fraction, Fraction]:
        if not 0 < propensity < 1:
            raise ValueError("propensity must be in (0,1)")
        odds = propensity / (1 - propensity)
        low_odds = odds / self.value
        high_odds = odds * self.value
        return low_odds / (1 + low_odds), high_odds / (1 + high_odds)
