from .calibration import Calibration
from .refusal import Refused


def current_calibration(calibrations: tuple[Calibration, ...]) -> Calibration:
    if not calibrations:
        raise Refused("NO_CALIBRATION")
    generation = max(item.generation for item in calibrations)
    current = [item for item in calibrations if item.generation == generation]
    digests = {item.digest for item in current}
    if len(digests) != 1:
        raise Refused("DIVERGENT_CURRENT_CALIBRATION")
    return current[0]
