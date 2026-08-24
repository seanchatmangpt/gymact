from __future__ import annotations

from dataclasses import dataclass

@dataclass(frozen=True)
class Qualification:
    standing: str
    calibration_rmse: float
    providers: int


def qualify(calibration_rmse: float, providers: int, dependency_standings: list[str]) -> Qualification:
    if "BUILD_BROKEN" in dependency_standings:
        return Qualification("BUILD_BROKEN", calibration_rmse, providers)
    if "BLOCKED" in dependency_standings:
        return Qualification("BLOCKED", calibration_rmse, providers)
    if providers < 2 or calibration_rmse > 0.25:
        return Qualification("UNKNOWN", calibration_rmse, providers)
    return Qualification("PARTIAL_ALIVE", calibration_rmse, providers)
