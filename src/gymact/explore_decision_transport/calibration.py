from dataclasses import dataclass
from fractions import Fraction

from .refusal import Refused


@dataclass(frozen=True, slots=True)
class Calibration:
    generation: int
    digest: str
    predicted: Fraction
    realized: Fraction
    support: int

    @property
    def gap(self) -> Fraction:
        return abs(self.predicted - self.realized)

    def admitted(self, *, min_support: int, max_gap: Fraction) -> bool:
        if self.generation < 0 or self.support < 0:
            raise Refused("INVALID_CALIBRATION")
        return self.support >= min_support and self.gap <= max_gap
