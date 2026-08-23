from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from .errors import require


@dataclass(frozen=True)
class Cusum:
    reference: Fraction
    threshold: Fraction

    def __post_init__(self) -> None:
        require(self.threshold > 0, "INVALID_DRIFT_THRESHOLD")

    def scan(self, samples: tuple[Fraction, ...]) -> tuple[int | None, Fraction]:
        score = Fraction(0)
        for index, sample in enumerate(samples):
            require(0 <= sample <= 1, "INVALID_DRIFT_SAMPLE")
            score = max(Fraction(0), score + sample - self.reference)
            if score >= self.threshold:
                return index, score
        return None, score
