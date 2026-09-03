from dataclasses import dataclass
from fractions import Fraction

from .calibration import Calibration
from .standing import Standing, derive


@dataclass(frozen=True, slots=True)
class Qualification:
    standing: Standing
    reason: str


def qualify(
    calibration: Calibration,
    dependencies: list[Standing],
    *,
    min_support: int,
    max_gap: Fraction,
) -> Qualification:
    calibrated = calibration.admitted(min_support=min_support, max_gap=max_gap)
    standing = derive(calibrated=calibrated, dependencies=dependencies)
    reason = (
        "failure-dominant dependency"
        if standing is Standing.BUILD_BROKEN
        else "transport evidence bounded"
    )
    return Qualification(standing, reason)
