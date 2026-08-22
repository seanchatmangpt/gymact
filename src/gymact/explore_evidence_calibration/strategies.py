from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from .estimate import CalibrationEstimate
from .likelihood import contribution
from .witness import CurrentWitness

class FusionStrategy(str, Enum):
    UNIFORM_CLUSTER = "UNIFORM_CLUSTER"
    CALIBRATED_LOG_ODDS = "CALIBRATED_LOG_ODDS"
    MINIMAX_UNDER_SUPPORT = "MINIMAX_UNDER_SUPPORT"

@dataclass(frozen=True)
class FusionResult:
    strategy: FusionStrategy
    score: int
    under_calibrated: tuple[str, ...]
    failures: int

def evaluate(strategy: FusionStrategy, witnesses: tuple[CurrentWitness, ...], estimates: dict[str, CalibrationEstimate]) -> FusionResult:
    failures = sum(w.outcome == "FAIL" for w in witnesses)
    under = tuple(sorted({w.source_id for w in witnesses if not estimates.get(w.source_id) or not estimates[w.source_id].calibrated}))
    if strategy is FusionStrategy.UNIFORM_CLUSTER:
        score = sum(1 if w.outcome == "PASS" else -1 if w.outcome == "FAIL" else 0 for w in witnesses)
    elif strategy is FusionStrategy.CALIBRATED_LOG_ODDS:
        score = sum(contribution(w, estimates.get(w.source_id)).milli_nats for w in witnesses)
    else:
        score = sum(contribution(w, estimates.get(w.source_id)).milli_nats for w in witnesses) - 1000*len(under)
    return FusionResult(strategy, score, under, failures)
