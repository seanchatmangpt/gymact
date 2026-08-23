from dataclasses import dataclass
from .calibration import Calibration
from .refusals import Refused

@dataclass(frozen=True)
class CalibrationVersion:
    generation: int
    digest: str
    calibration: Calibration


def current_frontier(versions: tuple[CalibrationVersion, ...]) -> tuple[CalibrationVersion, ...]:
    if not versions:
        raise Refused("NO_CALIBRATION_FRONTIER")
    generation = max(v.generation for v in versions)
    current = tuple(v for v in versions if v.generation == generation)
    digests = {v.digest for v in current}
    if len(digests) != len(current):
        raise Refused("DUPLICATE_CURRENT_CALIBRATION")
    modes = [v.calibration.mode for v in current]
    if len(set(modes)) != len(modes):
        raise Refused("DIVERGENT_CURRENT_CALIBRATION")
    return tuple(sorted(current, key=lambda v: v.calibration.mode.value))
