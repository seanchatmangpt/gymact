from dataclasses import dataclass
from fractions import Fraction

from .composition import CompositionMode
from .interval import Interval
from .refusals import Refused


@dataclass(frozen=True)
class CompositionCase:
    case_id: str
    mode: CompositionMode
    predicted: Interval
    truth: Fraction

    @property
    def covered(self) -> bool:
        return self.predicted.lower <= self.truth <= self.predicted.upper


@dataclass(frozen=True)
class Calibration:
    mode: CompositionMode
    support: int
    coverage: Fraction
    mean_width: Fraction

    @classmethod
    def from_cases(cls, mode: CompositionMode, cases: tuple[CompositionCase, ...]) -> "Calibration":
        chosen = tuple(case for case in cases if case.mode is mode)
        if len({case.case_id for case in chosen}) != len(chosen):
            raise Refused("DUPLICATE_CALIBRATION_CASE")
        if not chosen:
            raise Refused("NO_CALIBRATION_SUPPORT")
        coverage = Fraction(sum(case.covered for case in chosen), len(chosen))
        width = sum((case.predicted.width for case in chosen), Fraction(0)) / len(chosen)
        return cls(mode, len(chosen), coverage, width)
