from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from .refusal import require


@dataclass(frozen=True, slots=True)
class Calibration:
    support: int
    mean_absolute_error: Fraction
    generation: int
    digest: str

    def __post_init__(self) -> None:
        require(self.support > 0, "INSUFFICIENT_CALIBRATION_SUPPORT", "support must be positive")
        require(self.mean_absolute_error >= 0, "INVALID_CALIBRATION", "error must be nonnegative")
        require(self.generation >= 0, "INVALID_CALIBRATION", "generation must be nonnegative")
        require(len(self.digest) >= 16, "INVALID_CALIBRATION", "digest too short")


def current(calibrations: tuple[Calibration, ...]) -> Calibration:
    require(bool(calibrations), "MISSING_CALIBRATION", "no calibration evidence")
    generation = max(c.generation for c in calibrations)
    latest = tuple(c for c in calibrations if c.generation == generation)
    require(
        len({c.digest for c in latest}) == 1,
        "DIVERGENT_CURRENT_CALIBRATION",
        "latest generation split",
    )
    return latest[0]
