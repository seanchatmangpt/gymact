"""Scoring remains an explicit layer above independent verification."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from gymact.models import Score, VerificationResult


@runtime_checkable
class Scorer(Protocol):
    """Benchmark-owned scoring policy; verification never implies a score."""

    def score(self, verification: VerificationResult) -> tuple[Score, ...]: ...


class BinaryVerificationScorer:
    """Reference scorer mapping independent verification to a unitless binary metric."""

    def __init__(self, metric: str = "goal_satisfaction") -> None:
        self.metric = metric

    def score(self, verification: VerificationResult) -> tuple[Score, ...]:
        return (
            Score(
                metric=self.metric,
                value=1.0 if verification.passed else 0.0,
                unit="1",
            ),
        )


def score_verification(
    verification: VerificationResult,
    scorer: Scorer | None = None,
) -> tuple[Score, ...]:
    """Score a verification using an explicit benchmark policy."""
    return (scorer or BinaryVerificationScorer()).score(verification)
