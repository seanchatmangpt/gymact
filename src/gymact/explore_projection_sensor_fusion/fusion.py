from dataclasses import dataclass
from fractions import Fraction
from statistics import median

from .calibration import Calibration
from .refusals import FusionRefused


@dataclass(frozen=True, slots=True)
class FusedCalibration:
    false_current: Fraction
    false_stale: Fraction
    ambiguity: Fraction
    sensor_count: int


def robust_median(calibrations: tuple[Calibration, ...]) -> FusedCalibration:
    if len(calibrations) < 2:
        raise FusionRefused("REFUSED_INSUFFICIENT_FUSION_SENSORS")
    return FusedCalibration(
        Fraction(median([c.false_current for c in calibrations])),
        Fraction(median([c.false_stale for c in calibrations])),
        Fraction(median([c.ambiguity for c in calibrations])),
        len(calibrations),
    )
