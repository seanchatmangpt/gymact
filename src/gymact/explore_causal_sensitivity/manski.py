from dataclasses import dataclass
from fractions import Fraction


@dataclass(frozen=True)
class Interval:
    lower: Fraction
    upper: Fraction

    def width(self) -> Fraction:
        return self.upper - self.lower


def manski_mean(
    observed_sum: Fraction,
    observed_n: int,
    missing_n: int,
    lower: Fraction,
    upper: Fraction,
) -> Interval:
    if observed_n < 0 or missing_n < 0 or observed_n + missing_n == 0:
        raise ValueError("non-empty non-negative counts required")
    if lower > upper:
        raise ValueError("invalid bounds")
    total = observed_n + missing_n
    return Interval(
        (observed_sum + missing_n * lower) / total,
        (observed_sum + missing_n * upper) / total,
    )
