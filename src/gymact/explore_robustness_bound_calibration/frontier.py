from __future__ import annotations

import re
from dataclasses import dataclass

from .calibration import Calibration
from .refusal import REFUSED_DIVERGENT_FRONTIER, REFUSED_STALE_CALIBRATION, Refused

_HEX64 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class CalibrationSnapshot:
    generation: int
    digest: str
    model_digest: str
    calibration: Calibration

    def __post_init__(self) -> None:
        if self.generation < 0 or not _HEX64.fullmatch(self.digest):
            raise ValueError("invalid calibration snapshot identity")


def current(snapshots: tuple[CalibrationSnapshot, ...]) -> CalibrationSnapshot:
    if not snapshots:
        raise Refused(REFUSED_STALE_CALIBRATION, "empty frontier")
    generation = max(item.generation for item in snapshots)
    latest = tuple(item for item in snapshots if item.generation == generation)
    if len({item.digest for item in latest}) != 1:
        raise Refused(REFUSED_DIVERGENT_FRONTIER, str(generation))
    return latest[0]


def require_current(
    candidate: CalibrationSnapshot,
    snapshots: tuple[CalibrationSnapshot, ...],
) -> None:
    if candidate != current(snapshots):
        raise Refused(REFUSED_STALE_CALIBRATION, candidate.digest)
