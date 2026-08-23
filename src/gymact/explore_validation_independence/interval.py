from dataclasses import dataclass
from fractions import Fraction

from .refusal import Refused


@dataclass(frozen=True)
class Interval:
    low: Fraction
    high: Fraction

    def __post_init__(self) -> None:
        if not (Fraction(0) <= self.low <= self.high <= Fraction(1)):
            raise Refused("INVALID_INTERVAL", f"{self.low}..{self.high}")

    @property
    def width(self) -> Fraction:
        return self.high - self.low

    def frechet_and(self, other: "Interval") -> "Interval":
        return Interval(
            max(Fraction(0), self.low + other.low - 1), min(self.high, other.high)
        )

    def independent_and(self, other: "Interval") -> "Interval":
        return Interval(self.low * other.low, self.high * other.high)
