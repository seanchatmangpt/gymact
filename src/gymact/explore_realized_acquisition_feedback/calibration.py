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
        mean_error = sum(errors, Fraction(0)) / n
        mean_abs_error = sum((abs(error) for error in errors), Fraction(0)) / n
        return cls(n, mean_error, mean_abs_error)

    @property
    def calibrated(self) -> bool:
        return self.support >= 3
