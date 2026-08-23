from collections import defaultdict

from .calibration import Calibration
from .refusals import FusionRefused


def current_frontier(calibrations: tuple[Calibration, ...]) -> tuple[Calibration, ...]:
    by_sensor: dict[str, list[Calibration]] = defaultdict(list)
    for calibration in calibrations:
        by_sensor[calibration.sensor.sensor_id].append(calibration)
    selected: list[Calibration] = []
    for rows in by_sensor.values():
        generation = max(row.sensor.generation for row in rows)
        current = [row for row in rows if row.sensor.generation == generation]
        digests = {row.sensor.calibration_digest for row in current}
        if len(digests) != 1:
            raise FusionRefused("REFUSED_DIVERGENT_CURRENT_CALIBRATION")
        selected.append(current[0])
    return tuple(sorted(selected, key=lambda row: row.sensor.sensor_id))
