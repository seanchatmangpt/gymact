from dataclasses import dataclass
from fractions import Fraction

from .refusal import Refused


@dataclass(frozen=True)
class ValidationCase:
    case_id: str
    predicted_low: Fraction
    predicted_high: Fraction
    observed: Fraction

    @property
    def covered(self) -> bool:
        return self.predicted_low <= self.observed <= self.predicted_high


@dataclass(frozen=True)
class Calibration:
    generation: int
    support: int
    coverage: Fraction
    mean_width: Fraction
    digest: str

    @classmethod
    def from_cases(
        cls, generation: int, digest: str, cases: tuple[ValidationCase, ...]
    ) -> "Calibration":
        if not cases:
            raise Refused("INSUFFICIENT_CALIBRATION_SUPPORT")
        if len({case.case_id for case in cases}) != len(cases):
            raise Refused("DUPLICATE_CALIBRATION_CASE")
        covered = sum(case.covered for case in cases)
        widths = sum(
            (case.predicted_high - case.predicted_low for case in cases), Fraction(0)
        )
        return cls(
            generation,
            len(cases),
            Fraction(covered, len(cases)),
            widths / len(cases),
            digest,
        )
