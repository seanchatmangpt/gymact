from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from .refusals import refuse


@dataclass(frozen=True, slots=True)
class Calibration:
    generation: int
    digest: str
    support: int
    miss_rate: Fraction
    mean_width: Fraction

    def __post_init__(self) -> None:
        if self.generation < 0 or self.support <= 0 or not self.digest:
            raise refuse("INVALID_CALIBRATION", "generation, digest, and positive support are required")
        if not 0 <= self.miss_rate <= 1 or self.mean_width < 0:
            raise refuse("INVALID_CALIBRATION", "miss rate must be in [0,1] and width nonnegative")


def current(calibrations: tuple[Calibration, ...]) -> Calibration:
    if not calibrations:
        raise refuse("MISSING_CALIBRATION", "no ambiguity calibration supplied")
    generation = max(item.generation for item in calibrations)
    latest = tuple(item for item in calibrations if item.generation == generation)
    digests = {item.digest for item in latest}
    if len(digests) != 1:
        raise refuse("DIVERGENT_CURRENT_CALIBRATION", "latest generation has multiple digests")
    return min(latest, key=lambda item: (item.miss_rate, item.mean_width, -item.support))
