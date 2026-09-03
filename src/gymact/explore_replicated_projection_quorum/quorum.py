from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction

from .replica import ReplicaProjection
from .universe import ReplicaUniverse


class QuorumState(StrEnum):
    HEALTHY = "HEALTHY"
    PARTIAL_VISIBILITY = "PARTIAL_VISIBILITY"
    SPLIT_BRAIN = "SPLIT_BRAIN"
    STALE_MAJORITY = "STALE_MAJORITY"
    NO_QUORUM = "NO_QUORUM"


@dataclass(frozen=True, slots=True)
class QuorumAssessment:
    state: QuorumState
    standing: str
    coverage: Fraction
    highest_generation: int | None
    selected_generation: int | None
    selected_projection_digest: str | None
    agreeing_replicas: tuple[str, ...]


def assess_quorum(
    observations: tuple[ReplicaProjection, ...], universe: ReplicaUniverse
) -> QuorumAssessment:
    coverage = universe.coverage({item.replica_id for item in observations})
    if len(observations) < universe.quorum_size:
        return QuorumAssessment(
            QuorumState.PARTIAL_VISIBILITY, "UNKNOWN", coverage, None, None, None, ()
        )
    highest = max(item.generation for item in observations)
    highest_items = [item for item in observations if item.generation == highest]
    highest_digests = {item.projection_digest for item in highest_items}
    if len(highest_digests) > 1:
        return QuorumAssessment(
            QuorumState.SPLIT_BRAIN, "BLOCKED", coverage, highest, None, None, ()
        )
    counts = Counter((item.generation, item.projection_digest) for item in observations)
    (generation, digest), count = max(
        counts.items(), key=lambda item: (item[1], item[0][0], item[0][1])
    )
    agreeing = tuple(
        sorted(
            item.replica_id
            for item in observations
            if item.generation == generation and item.projection_digest == digest
        )
    )
    if count < universe.quorum_size:
        return QuorumAssessment(QuorumState.NO_QUORUM, "UNKNOWN", coverage, highest, None, None, ())
    if generation < highest:
        return QuorumAssessment(
            QuorumState.STALE_MAJORITY, "UNKNOWN", coverage, highest, generation, digest, agreeing
        )
    return QuorumAssessment(
        QuorumState.HEALTHY, "PARTIAL_ALIVE", coverage, highest, generation, digest, agreeing
    )
