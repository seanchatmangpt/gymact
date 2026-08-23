from collections.abc import Iterable
from dataclasses import dataclass

from .decision import Decision
from .errors import Refused


@dataclass(frozen=True, slots=True)
class CalibrationPoint:
    decision: Decision
    predicted_loss: float
    realized_loss: float


@dataclass(frozen=True, slots=True)
class DecisionRealizationCalibration:
    generation: int
    digest: str
    support: int
    mean_absolute_error: float
    mean_realized_loss: float

    @property
    def admitted(self) -> bool:
        return self.support >= 4 and self.mean_absolute_error <= 0.25


def calibrate(
    generation: int,
    digest: str,
    points: Iterable[CalibrationPoint],
) -> DecisionRealizationCalibration:
    rows = tuple(points)
    if generation < 0 or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise Refused("INVALID_CALIBRATION_IDENTITY")
    if not rows:
        raise Refused("INSUFFICIENT_REALIZATION_SUPPORT")
    if any(not 0.0 <= point.predicted_loss <= 1.0 or point.realized_loss < 0 for point in rows):
        raise Refused("INVALID_CALIBRATION_POINT")
    mae = sum(abs(point.predicted_loss - point.realized_loss) for point in rows) / len(rows)
    mean_loss = sum(point.realized_loss for point in rows) / len(rows)
    return DecisionRealizationCalibration(generation, digest, len(rows), mae, mean_loss)
