from collections.abc import Iterable

from .calibration import DecisionRealizationCalibration
from .errors import Refused


def current_calibration(
    items: Iterable[DecisionRealizationCalibration],
) -> DecisionRealizationCalibration:
    rows = tuple(items)
    if not rows:
        raise Refused("NO_REALIZATION_CALIBRATION")
    generation = max(row.generation for row in rows)
    latest = tuple(row for row in rows if row.generation == generation)
    digests = {row.digest for row in latest}
    if len(digests) != 1:
        raise Refused("DIVERGENT_CURRENT_REALIZATION_CALIBRATION")
    return max(latest, key=lambda row: (row.support, -row.mean_absolute_error))
