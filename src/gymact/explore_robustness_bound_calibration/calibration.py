from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from .case import BoundCase
from .refusal import REFUSED_INSUFFICIENT_SUPPORT, Refused


@dataclass(frozen=True, slots=True)
class Calibration:
    support: int
    coverage: Fraction
    miss_rate: Fraction
    mean_width: Fraction

    @classmethod
    def from_cases(
        cls, cases: tuple[BoundCase, ...], minimum_support: int = 3
    ) -> Calibration:
        if len(cases) < minimum_support:
            raise Refused(REFUSED_INSUFFICIENT_SUPPORT, f"{len(cases)}<{minimum_support}")
        ids = [case.case_id for case in cases]
        if len(ids) != len(set(ids)):
            raise Refused(REFUSED_INSUFFICIENT_SUPPORT, "duplicate cases")
        covered = sum(case.covered for case in cases)
        support = len(cases)
        coverage = Fraction(covered, support)
        mean_width = sum((case.bound.width for case in cases), Fraction(0)) / support
        return cls(support, coverage, 1 - coverage, mean_width)

    def reliable(self, *, minimum_coverage: Fraction, maximum_width: Fraction) -> bool:
        return self.coverage >= minimum_coverage and self.mean_width <= maximum_width
