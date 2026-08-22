from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .strategies import FusionResult


class Decision(StrEnum):
    ACCEPT_BOUNDED = "ACCEPT_BOUNDED"
    REJECT = "REJECT"
    CONTINUE = "CONTINUE"


@dataclass(frozen=True)
class SequentialDecision:
    decision: Decision
    standing: str
    score: int


def decide(
    result: FusionResult,
    *,
    accept_threshold: int = 1000,
    reject_threshold: int = -1000,
) -> SequentialDecision:
    if result.failures:
        return SequentialDecision(Decision.REJECT, "BUILD_BROKEN", result.score)
    if result.under_calibrated:
        return SequentialDecision(Decision.CONTINUE, "UNKNOWN", result.score)
    if result.score >= accept_threshold:
        return SequentialDecision(Decision.ACCEPT_BOUNDED, "PARTIAL_ALIVE", result.score)
    if result.score <= reject_threshold:
        return SequentialDecision(Decision.REJECT, "BUILD_BROKEN", result.score)
    return SequentialDecision(Decision.CONTINUE, "UNKNOWN", result.score)
