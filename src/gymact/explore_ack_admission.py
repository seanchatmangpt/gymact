from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .explore_ack_identity import Subject
from .explore_ack_invalidation import Invalidation
from .explore_ack_witness import Witness, WitnessKind

_ORDER = {
    WitnessKind.DELIVERED: 1,
    WitnessKind.ACKNOWLEDGED: 2,
    WitnessKind.DISCHARGED: 3,
}


@dataclass(frozen=True)
class Admission:
    frontier: dict[str, WitnessKind]
    duplicates: int


def admit(
    event: Invalidation,
    affected: tuple[Subject, ...],
    witnesses: tuple[Witness, ...],
) -> Admission:
    keys = {c.key for c in affected}
    by_consumer: dict[str, list[Witness]] = defaultdict(list)
    seen: set[tuple[str, WitnessKind, int, str]] = set()
    duplicates = 0
    for witness in witnesses:
        if witness.event_id != event.event_id:
            raise ValueError("REFUSED_WITNESS_EVENT_MISMATCH")
        if witness.consumer.key not in keys:
            raise ValueError("REFUSED_ORPHAN_WITNESS")
        signature = (witness.consumer.key, witness.kind, witness.sequence, witness.digest)
        if signature in seen:
            duplicates += 1
            continue
        seen.add(signature)
        by_consumer[witness.consumer.key].append(witness)
    frontier: dict[str, WitnessKind] = {}
    for key, items in by_consumer.items():
        ordered = sorted(items, key=lambda item: item.sequence)
        previous = 0
        for item in ordered:
            rank = _ORDER[item.kind]
            if rank < previous:
                raise ValueError("REFUSED_CAUSAL_REGRESSION")
            if rank > previous + 1:
                raise ValueError("REFUSED_CAUSAL_GAP")
            previous = rank
        frontier[key] = ordered[-1].kind
    return Admission(frontier=frontier, duplicates=duplicates)
