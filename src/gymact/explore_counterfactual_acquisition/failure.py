from dataclasses import dataclass
import random
from typing import Iterable

from .logged import LoggedDecision


@dataclass(frozen=True, slots=True)
class FailureWorld:
    support_dropout: tuple[str, ...]
    propensity_misspecification: tuple[str, ...]
    hidden_confounding_flag: tuple[str, ...]


def world(decisions: Iterable[LoggedDecision], *, seed: int) -> FailureWorld:
    rows = sorted(decisions, key=lambda row: row.decision_id)
    rng = random.Random(seed)
    dropout: list[str] = []
    misspecified: list[str] = []
    confounded: list[str] = []
    for row in rows:
        draw = rng.random()
        if draw < 0.20:
            dropout.append(row.decision_id)
        elif draw < 0.40:
            misspecified.append(row.decision_id)
        elif draw < 0.55:
            confounded.append(row.decision_id)
    return FailureWorld(tuple(dropout), tuple(misspecified), tuple(confounded))
