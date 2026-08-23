from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from .refusal import Refused
from .replica import ReplicaProjection
from .subject import Subject
from .universe import ReplicaUniverse
from .window import ObservationWindow


def admit_observations(
    observations: Iterable[ReplicaProjection],
    *,
    subject: Subject,
    semantic_digest: str,
    universe: ReplicaUniverse,
    window: ObservationWindow,
    now: datetime,
) -> tuple[ReplicaProjection, ...]:
    if now.tzinfo is None or now.utcoffset() is None:
        raise Refused("REFUSED_NAIVE_NOW")
    admitted: list[ReplicaProjection] = []
    seen: set[str] = set()
    allowed = set(universe.replica_ids)
    for observation in observations:
        if observation.subject != subject:
            raise Refused("REFUSED_FOREIGN_SUBJECT")
        if observation.semantic_digest != semantic_digest:
            raise Refused("REFUSED_SEMANTIC_DRIFT")
        if observation.replica_id not in allowed:
            raise Refused("REFUSED_FOREIGN_REPLICA")
        if observation.replica_id in seen:
            raise Refused("REFUSED_DUPLICATE_REPLICA_OBSERVATION")
        if observation.observed_at > now:
            raise Refused("REFUSED_FUTURE_PROJECTION_EVIDENCE")
        if not window.contains(observation.observed_at):
            raise Refused("REFUSED_OUT_OF_WINDOW_PROJECTION_EVIDENCE")
        seen.add(observation.replica_id)
        admitted.append(observation)
    return tuple(sorted(admitted, key=lambda item: item.replica_id))
