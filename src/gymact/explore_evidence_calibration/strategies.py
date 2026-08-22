from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .estimate import CalibrationEstimate
from .likelihood import contribution
from .witness import CurrentWitness


class FusionStrategy(StrEnum):
    UNIFORM_CLUSTER = "UNIFORM_CLUSTER"
    CALIBRATED_LOG_ODDS = "CALIBRATED_LOG_ODDS"
    MINIMAX_UNDER_SUPPORT = "MINIMAX_UNDER_SUPPORT"


@dataclass(frozen=True)
class FusionResult:
    strategy: FusionStrategy
    score: int
    under_calibrated: tuple[str, ...]
    failures: int


def evaluate(
    strategy: FusionStrategy,
    witnesses: tuple[CurrentWitness, ...],
    estimates: dict[str, CalibrationEstimate],
) -> FusionResult:
    failures = sum(witness.outcome == "FAIL" for witness in witnesses)
    under_calibrated = tuple(
        sorted(
            {
                witness.source_id
                for witness in witnesses
                if not estimates.get(witness.source_id)
                or not estimates[witness.source_id].calibrated
            }
        )
    )
    if strategy is FusionStrategy.UNIFORM_CLUSTER:
        score = sum(
            1 if witness.outcome == "PASS" else -1 if witness.outcome == "FAIL" else 0
            for witness in witnesses
        )
    elif strategy is FusionStrategy.CALIBRATED_LOG_ODDS:
        score = sum(
            contribution(witness, estimates.get(witness.source_id)).milli_nats
            for witness in witnesses
        )
    else:
        known = sum(
            contribution(witness, estimates.get(witness.source_id)).milli_nats
            for witness in witnesses
        )
        score = known - 1000 * len(under_calibrated)
    return FusionResult(strategy, score, under_calibrated, failures)
