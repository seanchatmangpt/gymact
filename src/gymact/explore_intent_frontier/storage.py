from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class StoreKind(StrEnum):
    MEMORY = "MEMORY"
    JSONL = "JSONL"
    SQLITE = "SQLITE"


@dataclass(frozen=True, slots=True)
class StoreCandidate:
    kind: StoreKind
    durable: bool
    transactional: bool
    external: bool = False


def discover() -> tuple[StoreCandidate, ...]:
    return (
        StoreCandidate(StoreKind.MEMORY, False, False),
        StoreCandidate(StoreKind.JSONL, True, False),
        StoreCandidate(StoreKind.SQLITE, True, True),
    )


def select(*, durable: bool, transactional: bool) -> StoreCandidate:
    viable = [
        c
        for c in discover()
        if (not durable or c.durable) and (not transactional or c.transactional)
    ]
    if not viable:
        raise ValueError("REFUSED_NO_LAWFUL_STORE_CANDIDATE")
    rank = {StoreKind.MEMORY: 0, StoreKind.JSONL: 1, StoreKind.SQLITE: 2}
    return min(viable, key=lambda c: rank[c.kind])
