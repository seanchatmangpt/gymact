from dataclasses import dataclass

from .calibration import Calibration
from .refusals import Refused


@dataclass(frozen=True)
class CalibrationVersion:
    generation: int
    digest: str
    calibration: Calibration


def current_frontier(
    versions: tuple[CalibrationVersion, ...],
) -> tuple[CalibrationVersion, ...]:
    if not versions:
        raise Refused("NO_CALIBRATION_FRONTIER")
    generation = max(version.generation for version in versions)
    current = tuple(version for version in versions if version.generation == generation)
    digests = {version.digest for version in current}
    if len(digests) != len(current):
        raise Refused("DUPLICATE_CURRENT_CALIBRATION")
    modes = [version.calibration.mode for version in current]
    if len(set(modes)) != len(modes):
        raise Refused("DIVERGENT_CURRENT_CALIBRATION")
    return tuple(sorted(current, key=lambda version: version.calibration.mode.value))
