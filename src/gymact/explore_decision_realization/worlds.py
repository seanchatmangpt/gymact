from dataclasses import dataclass
from enum import StrEnum

from .standing import Standing


class FailureWorld(StrEnum):
    SELECTIVE_LABEL_DROPOUT = "SELECTIVE_LABEL_DROPOUT"
    POLICY_DRIFT = "POLICY_DRIFT"
    OUTCOME_DELAY = "OUTCOME_DELAY"
    SHARED_OBSERVER = "SHARED_OBSERVER"
    DEPENDENCY_FAILURE = "DEPENDENCY_FAILURE"
    AMBIGUOUS_DO = "AMBIGUOUS_DO"
    REPLAY_TAMPER = "REPLAY_TAMPER"


@dataclass(frozen=True, slots=True)
class World:
    name: FailureWorld
    dependency_standing: Standing
    observation_probability: float
    drifted: bool


def canonical_worlds() -> tuple[World, ...]:
    return (
        World(FailureWorld.SELECTIVE_LABEL_DROPOUT, Standing.ALIVE, 0.2, False),
        World(FailureWorld.POLICY_DRIFT, Standing.ALIVE, 1.0, True),
        World(FailureWorld.OUTCOME_DELAY, Standing.UNKNOWN, 0.5, False),
        World(FailureWorld.SHARED_OBSERVER, Standing.PARTIAL_ALIVE, 0.7, False),
        World(FailureWorld.DEPENDENCY_FAILURE, Standing.BUILD_BROKEN, 1.0, False),
        World(FailureWorld.AMBIGUOUS_DO, Standing.BLOCKED, 1.0, False),
        World(FailureWorld.REPLAY_TAMPER, Standing.PARTIAL_ALIVE, 1.0, False),
    )
