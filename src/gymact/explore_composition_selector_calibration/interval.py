from dataclasses import dataclass
from fractions import Fraction

from .refusals import Refused


@dataclass(frozen=True, order=True)
class Interval:
    lower: Fraction
    upper: Fraction

    def __post_init__(self) -> None:
        if not (Fraction(0) <= self.lower <= self.upper <= Fraction(1)):
            raise Refused("INVALID_INTERVAL", f"{self.lower},{self.upper}")

    @property
    def width(self) -> Fraction:
        return self.upper - self.lower

    def frechet_and(self, other: "Interval") -> "Interval":
        return Interval(
            max(Fraction(0), self.lower + other.lower - 1),
            min(self.upper, other.upper),
        )

    def independent_and(self, other: "Interval") -> "Interval":
        return Interval(self.lower * other.lower, self.upper * other.upper)
