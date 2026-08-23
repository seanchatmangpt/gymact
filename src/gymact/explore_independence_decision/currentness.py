from __future__ import annotations

from .calibration import DecisionCalibration
from .errors import Refused


def current(calibrations: tuple[DecisionCalibration, ...]) -> DecisionCalibration:
    if not calibrations:
        raise Refused("MISSING_CALIBRATION")
    generation = max(item.generation for item in calibrations)
    latest = [item for item in calibrations if item.generation == generation]
    digests = {item.digest for item in latest}
    if len(digests) != 1:
        raise Refused("DIVERGENT_CURRENT_CALIBRATION")
    return sorted(latest, key=lambda item: item.digest)[0]
