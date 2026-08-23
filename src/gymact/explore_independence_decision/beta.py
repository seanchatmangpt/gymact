from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from .errors import require


@dataclass(frozen=True)
class BetaEvidence:
    successes: int
    failures: int
    alpha0: int = 1
    beta0: int = 1

    def __post_init__(self) -> None:
        require(self.successes >= 0 and self.failures >= 0, "NEGATIVE_COUNTS")
        require(self.alpha0 > 0 and self.beta0 > 0, "INVALID_PRIOR")

    @property
    def alpha(self) -> int:
        return self.alpha0 + self.successes

    @property
    def beta(self) -> int:
        return self.beta0 + self.failures

    @property
    def mean(self) -> Fraction:
        return Fraction(self.alpha, self.alpha + self.beta)

    @property
    def support(self) -> int:
        return self.successes + self.failures

    def predictive_success(self) -> Fraction:
        return self.mean
