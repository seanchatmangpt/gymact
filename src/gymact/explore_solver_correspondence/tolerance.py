from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from .refusal import Refused


@dataclass(frozen=True)
class NumericAdmission:
    tolerance: Fraction = Fraction(0)

    def __post_init__(self) -> None:
        if self.tolerance < 0:
            raise Refused("NEGATIVE_TOLERANCE")

    def admits(self, left: Fraction, right: Fraction) -> bool:
        return abs(left - right) <= self.tolerance

    def require(self, left: Fraction, right: Fraction) -> None:
        if not self.admits(left, right):
            raise Refused("NUMERIC_DIVERGENCE", str(abs(left - right)))
