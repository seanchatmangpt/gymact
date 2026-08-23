from dataclasses import dataclass
from enum import Enum
from fractions import Fraction
from .calibration import Calibration

class Selector(str, Enum):
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
        c = max(calibrations, key=lambda x: (x.coverage, -x.mean_width))
        return Selection(selector, c.mode.value, c.coverage)
    if selector is Selector.MIN_WIDTH:
        c = min(calibrations, key=lambda x: (x.mean_width, -x.coverage))
        return Selection(selector, c.mode.value, -c.mean_width)
    if selector is Selector.MINIMAX_MISS:
        c = min(calibrations, key=lambda x: (1 - x.coverage, x.mean_width))
        return Selection(selector, c.mode.value, -(1 - c.coverage))
    c = max(calibrations, key=lambda x: x.mean_width * x.coverage)
    return Selection(selector, c.mode.value, c.mean_width * c.coverage)
