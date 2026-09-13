from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction


@dataclass(frozen=True, slots=True)
class ControlCandidate:
    key: str
    expected_debt_reduction: Fraction
    regression_risk: Fraction
    blocker_relief: Fraction
    oscillation_risk: Fraction
    cost: Fraction

    def __post_init__(self) -> None:
        for value in (
            self.expected_debt_reduction,
            self.regression_risk,
            self.blocker_relief,
            self.oscillation_risk,
            self.cost,
        ):
            if value < 0:
                raise ValueError("closure-control metrics must be non-negative")
