from dataclasses import dataclass
from fractions import Fraction

from .refusals import FusionRefused
from .sensor import SensorIdentity


@dataclass(frozen=True, slots=True)
class Calibration:
    sensor: SensorIdentity
    support: int
    false_current: Fraction
    false_stale: Fraction
    ambiguity: Fraction

    def __post_init__(self) -> None:
        rates = (self.false_current, self.false_stale, self.ambiguity)
        if self.support < 0 or any(rate < 0 or rate > 1 for rate in rates):
            raise FusionRefused("REFUSED_INVALID_CALIBRATION")

    @property
    def error_mass(self) -> Fraction:
        return self.false_current + self.false_stale + self.ambiguity
