from dataclasses import dataclass
from fractions import Fraction

from .realization import AcquisitionRealization

@dataclass(frozen=True)
class GainCalibration:
    support: int
    mean_error: Fraction
    mean_abs_error: Fraction

    @classmethod
    def fit(cls, xs: list[AcquisitionRealization]) -> "GainCalibration":
        if not xs:
            return cls(0, Fraction(0), Fraction(0))
        errors = [x.gain_error for x in xs]
        n = len(errors)
        return cls(n, sum(errors, Fraction(0)) / n, sum((abs(e) for e in errors), Fraction(0)) / n)

    @property
    def calibrated(self) -> bool:
        return self.support >= 3
