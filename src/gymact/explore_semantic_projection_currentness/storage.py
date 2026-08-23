from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .subject import Refusal


class StorageKind(str, Enum):
    MEMORY = "MEMORY"
    JSONL = "JSONL"
    SQLITE = "SQLITE"


@dataclass(frozen=True, slots=True)
class StorageCapability:
    kind: StorageKind
    durable: bool
    transactional: bool
    replayable: bool


CANDIDATES = (
    StorageCapability(StorageKind.MEMORY, False, False, True),
    StorageCapability(StorageKind.JSONL, True, False, True),
    StorageCapability(StorageKind.SQLITE, True, True, True),
)


def select_storage(*, durable: bool, transactional: bool) -> StorageCapability:
    admitted = [
        c for c in CANDIDATES
        if (not durable or c.durable) and (not transactional or c.transactional)
    ]
    if not admitted:
        raise Refusal("REFUSED_NO_STORAGE_CANDIDATE")
    return sorted(admitted, key=lambda c: (c.transactional, c.durable, c.kind.value))[0]
