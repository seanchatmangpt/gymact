from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from .errors import require


@dataclass(frozen=True)
class LossMatrix:
    false_independent: Fraction
    false_dependent: Fraction
    defer: Fraction = Fraction(0)

    def __post_init__(self) -> None:
        require(self.false_independent >= 0, "NEGATIVE_FALSE_INDEPENDENT_LOSS")
        require(self.false_dependent >= 0, "NEGATIVE_FALSE_DEPENDENT_LOSS")
        require(self.defer >= 0, "NEGATIVE_DEFER_LOSS")

    def independent_risk(self, p_independent: Fraction) -> Fraction:
        return (1 - p_independent) * self.false_independent

    def dependent_risk(self, p_independent: Fraction) -> Fraction:
        return p_independent * self.false_dependent
