from fractions import Fraction

from .calibration import Calibration
from .fusion import robust_median
from .refusals import FusionRefused


def leave_one_out_influence(calibrations: tuple[Calibration, ...]) -> dict[str, Fraction]:
    if len(calibrations) < 3:
        raise FusionRefused("REFUSED_INSUFFICIENT_INFLUENCE_SENSORS")
    baseline = robust_median(calibrations)
    result: dict[str, Fraction] = {}
    for index, calibration in enumerate(calibrations):
        reduced = robust_median(calibrations[:index] + calibrations[index + 1 :])
        result[calibration.sensor.sensor_id] = abs(baseline.false_current - reduced.false_current) + abs(baseline.ambiguity - reduced.ambiguity)
    return result
