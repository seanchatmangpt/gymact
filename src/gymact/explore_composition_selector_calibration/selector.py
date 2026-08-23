from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction

from .calibration import Calibration


class Selector(StrEnum):
    MAX_COVERAGE = "MAX_COVERAGE"
    MIN_WIDTH = "MIN_WIDTH"
    MINIMAX_MISS = "MINIMAX_MISS"
    INFORMATION_GAIN = "INFORMATION_GAIN"


@dataclass(frozen=True)
class Selection:
    selector: Selector
    mode: str
    score: Fraction


def choose(calibrations: tuple[Calibration, ...], selector: Selector) -> Selection:
    if selector is Selector.MAX_COVERAGE:
        calibration = max(
            calibrations, key=lambda candidate: (candidate.coverage, -candidate.mean_width)
        )
        return Selection(selector, calibration.mode.value, calibration.coverage)
    if selector is Selector.MIN_WIDTH:
        calibration = min(
            calibrations, key=lambda candidate: (candidate.mean_width, -candidate.coverage)
        )
        return Selection(selector, calibration.mode.value, -calibration.mean_width)
    if selector is Selector.MINIMAX_MISS:
        calibration = min(
            calibrations,
            key=lambda candidate: (1 - candidate.coverage, candidate.mean_width),
        )
        return Selection(selector, calibration.mode.value, -(1 - calibration.coverage))
    calibration = max(
        calibrations, key=lambda candidate: candidate.mean_width * candidate.coverage
    )
    return Selection(
        selector,
        calibration.mode.value,
        calibration.mean_width * calibration.coverage,
    )
