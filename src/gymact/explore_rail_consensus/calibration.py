from dataclasses import dataclass
from fractions import Fraction

from .subject import Refusal

@dataclass(frozen=True, slots=True)
class RailCalibration:
    support: int
    false_alarm: Fraction
    miss_rate: Fraction
    median_delay: Fraction

    def __post_init__(self) -> None:
        if self.support < 0:
            raise Refusal("REFUSED_INVALID_CALIBRATION_SUPPORT")
        for metric in (self.false_alarm, self.miss_rate):
            if metric < 0 or metric > 1:
                raise Refusal("REFUSED_INVALID_CALIBRATION_RATE")
        if self.median_delay < 0:
            raise Refusal("REFUSED_INVALID_CALIBRATION_DELAY")

    def state(self, *, min_support: int = 4, max_false_alarm: Fraction = Fraction(1, 4), max_miss_rate: Fraction = Fraction(1, 4)) -> str:
        if self.support < min_support:
            return "INSUFFICIENT"
        if self.false_alarm > max_false_alarm or self.miss_rate > max_miss_rate:
            return "UNRELIABLE"
        return "CALIBRATED"
