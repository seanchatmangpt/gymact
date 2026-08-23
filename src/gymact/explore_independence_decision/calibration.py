from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from .errors import require


@dataclass(frozen=True)
class DecisionCalibration:
    support: int
    false_independent: int
    false_dependent: int
    generation: int
    digest: str

    def __post_init__(self) -> None:
        require(self.support > 0, "INSUFFICIENT_SUPPORT")
        require(0 <= self.false_independent <= self.support, "INVALID_FALSE_INDEPENDENT")
        require(0 <= self.false_dependent <= self.support, "INVALID_FALSE_DEPENDENT")
        require(self.generation >= 0, "INVALID_GENERATION")
        require(bool(self.digest), "MISSING_CALIBRATION_DIGEST")

    @property
    def false_independent_rate(self) -> Fraction:
        return Fraction(self.false_independent, self.support)

    @property
    def false_dependent_rate(self) -> Fraction:
        return Fraction(self.false_dependent, self.support)

    @property
    def accuracy_floor(self) -> Fraction:
        return 1 - self.false_independent_rate - self.false_dependent_rate
