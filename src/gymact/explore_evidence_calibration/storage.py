from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class StoreKind(StrEnum):
    MEMORY = "MEMORY"
    JSONL = "JSONL"
    SQLITE = "SQLITE"


@dataclass(frozen=True)
class StoreCandidate:
    kind: StoreKind
    durable: bool
    transactional: bool


def candidates() -> tuple[StoreCandidate, ...]:
    return (
        StoreCandidate(StoreKind.MEMORY, False, False),
        StoreCandidate(StoreKind.JSONL, True, False),
        StoreCandidate(StoreKind.SQLITE, True, True),
    )


def select(*, durable: bool, transactional: bool) -> StoreCandidate:
    viable = [
        candidate
        for candidate in candidates()
        if (not durable or candidate.durable)
        and (not transactional or candidate.transactional)
    ]
    return min(
        viable,
        key=lambda candidate: (
            candidate.durable, candidate.transactional, candidate.kind.value
        ),
    )
