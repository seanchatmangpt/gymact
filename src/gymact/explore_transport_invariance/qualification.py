from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from .calibration import Calibration
from .refusal import require
from .selectors import Candidate


@dataclass(frozen=True, slots=True)
class Qualification:
    candidate: Candidate
    calibration: Calibration
    worst_case_risk: Fraction
    standing: str


def qualify(
    candidate: Candidate,
    calibration: Calibration,
    stressed_risks: tuple[Fraction, ...],
    max_risk: Fraction,
) -> Qualification:
    require(
        bool(stressed_risks), "MISSING_STRESS_EVIDENCE", "at least one stress world is required"
    )
    worst = max(stressed_risks)
    require(candidate.support > 0, "NO_SUPPORT", "candidate has no support")
    standing = "PARTIAL_ALIVE" if worst <= max_risk else "UNSUPPORTED"
    return Qualification(candidate, calibration, worst, standing)
