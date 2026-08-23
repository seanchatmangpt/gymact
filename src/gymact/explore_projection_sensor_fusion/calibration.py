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
        if self.support < 0 or any(x < 0 or x > 1 for x in (self.false_current, self.false_stale, self.ambiguity)):
            raise FusionRefused("REFUSED_INVALID_CALIBRATION")

    @property
    def error_mass(self) -> Fraction:
        return self.false_current + self.false_stale + self.ambiguity
