from __future__ import annotations

import hashlib
import random
from dataclasses import replace
from enum import StrEnum

from .clock import VectorClock
from .replica import ReplicaProjection

class FailureKind(StrEnum):
    PARTITION = "PARTITION"
    STALE_REPLICA = "STALE_REPLICA"
    SPLIT_BRAIN = "SPLIT_BRAIN"
    OMISSION = "OMISSION"
    CLOCK_SKEW = "CLOCK_SKEW"

def inject_failure(
    observations: tuple[ReplicaProjection, ...], kind: FailureKind, seed: int
) -> tuple[ReplicaProjection, ...]:
    if not observations:
        return observations
    rng = random.Random(seed)
    items = list(observations)
    index = rng.randrange(len(items))
    if kind in {FailureKind.PARTITION, FailureKind.OMISSION}:
        del items[index]
    elif kind is FailureKind.STALE_REPLICA:
        item = items[index]
        items[index] = replace(item, generation=max(0, item.generation - 1))
    elif kind is FailureKind.SPLIT_BRAIN:
        item = items[index]
        digest = hashlib.sha256(f"{item.projection_digest}:{seed}".encode()).hexdigest()
        items[index] = replace(item, projection_digest=digest)
    else:
        item = items[index]
        clock = item.clock.as_dict()
        clock[item.replica_id] = clock.get(item.replica_id, 0) + 1
        items[index] = replace(item, clock=VectorClock.from_dict(clock))
    return tuple(sorted(items, key=lambda item: item.replica_id))
