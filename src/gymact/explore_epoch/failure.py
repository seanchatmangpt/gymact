from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass(frozen=True)
class FailureWorld:
    seed: int
    failed_consumers: frozenset[str]


def inject(consumers: tuple[str, ...], *, seed: int, probability: float) -> FailureWorld:
    if not 0.0 <= probability <= 1.0:
        raise ValueError("REFUSED_INVALID_FAILURE_PROBABILITY")
    rng = random.Random(seed)
    failed = frozenset(c for c in consumers if rng.random() < probability)
    return FailureWorld(seed, failed)
