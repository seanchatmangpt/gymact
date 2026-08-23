from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class StorageKind(StrEnum):
    MEMORY = "MEMORY"
    JSONL = "JSONL"
    SQLITE = "SQLITE"


@dataclass(frozen=True)
class StorageCandidate:
    kind: StorageKind
    durable: bool
    transactional: bool
    external_dependency: bool


def candidates() -> tuple[StorageCandidate, ...]:
    return (
        StorageCandidate(StorageKind.MEMORY, False, False, False),
        StorageCandidate(StorageKind.JSONL, True, False, False),
        StorageCandidate(StorageKind.SQLITE, True, True, False),
    )


def select(require_durable: bool, require_transactional: bool) -> StorageCandidate:
    lawful = [
        candidate
        for candidate in candidates()
        if (not require_durable or candidate.durable)
        and (not require_transactional or candidate.transactional)
    ]
    if not lawful:
        raise ValueError("REFUSED_NO_LAWFUL_STORAGE")
    return lawful[0]
