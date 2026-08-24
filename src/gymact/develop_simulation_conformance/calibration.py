from __future__ import annotations

from dataclasses import dataclass
from math import sqrt

@dataclass(frozen=True)
class Calibration:
    support: int
    mean_error: float
    rmse: float


def calibrate(predicted: list[float], realized: list[float]) -> Calibration:
    if len(predicted) != len(realized) or not predicted:
        raise ValueError("REFUSED[INVALID_CALIBRATION_SAMPLE]")
    errors = [p - r for p, r in zip(predicted, realized)]
    return Calibration(len(errors), sum(abs(e) for e in errors) / len(errors), sqrt(sum(e * e for e in errors) / len(errors)))
