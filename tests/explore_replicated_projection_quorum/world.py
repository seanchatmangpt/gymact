from __future__ import annotations

from datetime import datetime, timedelta, timezone

from gymact.explore_replicated_projection_quorum.clock import VectorClock
from gymact.explore_replicated_projection_quorum.replica import ReplicaProjection, Representation
from gymact.explore_replicated_projection_quorum.subject import Subject
from gymact.explore_replicated_projection_quorum.universe import ReplicaUniverse
from gymact.explore_replicated_projection_quorum.window import ObservationWindow

SUBJECT = Subject("seanchatmangpt/gymact@" + "1" * 40)
SEMANTIC = "a" * 64
PROJECTION = "b" * 64
NOW = datetime(2026, 8, 23, 1, 0, tzinfo=timezone.utc)
WINDOW = ObservationWindow(NOW - timedelta(hours=2), NOW + timedelta(seconds=1))
UNIVERSE = ReplicaUniverse(("r1", "r2", "r3", "r4", "r5"))

def projection(replica: str, generation: int = 2, digest: str = PROJECTION, clock: dict[str, int] | None = None) -> ReplicaProjection:
    return ReplicaProjection(
        subject=SUBJECT,
        replica_id=replica,
        generation=generation,
        semantic_digest=SEMANTIC,
        projection_digest=digest,
        representation=Representation.CANONICAL_JSON,
        clock=VectorClock.from_dict(clock or {replica: generation}),
        observed_at=NOW,
    )
