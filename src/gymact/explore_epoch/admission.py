from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .epoch import InvalidationEpoch
from .identity import Subject
from .witness import Witness, WitnessKind

_ORDER = {WitnessKind.DELIVERED: 1, WitnessKind.ACKNOWLEDGED: 2, WitnessKind.DISCHARGED: 3, WitnessKind.RECOVERED: 4}


@dataclass(frozen=True)
class Admission:
    frontier: dict[str, WitnessKind]
    pending: tuple[str, ...]


def admit(epoch: InvalidationEpoch, consumers: tuple[Subject, ...], witnesses: tuple[Witness, ...]) -> Admission:
    expected = {c.key for c in consumers}
    grouped: dict[str, list[Witness]] = defaultdict(list)
    for witness in witnesses:
        if witness.consumer.key not in expected:
            raise ValueError("REFUSED_ORPHAN_EPOCH_WITNESS")
        if witness.generation < epoch.generation:
            raise ValueError("REFUSED_STALE_INVALIDATION_EPOCH")
        if witness.generation > epoch.generation:
            raise ValueError("REFUSED_FUTURE_INVALIDATION_EPOCH")
        if witness.event_id != epoch.event_id:
            raise ValueError("REFUSED_EPOCH_EVENT_MISMATCH")
        grouped[witness.consumer.key].append(witness)

    frontier: dict[str, WitnessKind] = {}
    for key, records in grouped.items():
        records = sorted(records, key=lambda w: w.sequence)
        prior = 0
        prior_sequence: int | None = None
        for record in records:
            rank = _ORDER[record.kind]
            if rank > prior + 1:
                raise ValueError("REFUSED_CAUSAL_WITNESS_GAP")
            if rank < prior:
                raise ValueError("REFUSED_CAUSAL_WITNESS_REGRESSION")
            if rank > 1 and record.parent_sequence != prior_sequence:
                raise ValueError("REFUSED_CAUSAL_PARENT_MISMATCH")
            prior = max(prior, rank)
            prior_sequence = record.sequence
            frontier[key] = record.kind
    pending = tuple(sorted(expected - set(frontier)))
    return Admission(frontier=frontier, pending=pending)
