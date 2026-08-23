from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction

from .loss import LossMatrix


class Decision(StrEnum):
    INDEPENDENT = "INDEPENDENT"
    DEPENDENT = "DEPENDENT"
    DEFER = "DEFER"


@dataclass(frozen=True)
class DecisionResult:
    decision: Decision
    risk: Fraction
    independent_risk: Fraction
    dependent_risk: Fraction
    defer_risk: Fraction


def decide(p_independent: Fraction, loss: LossMatrix) -> DecisionResult:
    risks = {
        Decision.INDEPENDENT: loss.independent_risk(p_independent),
        Decision.DEPENDENT: loss.dependent_risk(p_independent),
        Decision.DEFER: loss.defer,
    }
    decision = min(risks, key=lambda item: (risks[item], item.value))
    return DecisionResult(
        decision=decision,
        risk=risks[decision],
        independent_risk=risks[Decision.INDEPENDENT],
        dependent_risk=risks[Decision.DEPENDENT],
        defer_risk=risks[Decision.DEFER],
    )
