from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .refusal import Refused


class StorageKind(StrEnum):
    MEMORY = "MEMORY"
    JSONL = "JSONL"
    SQLITE = "SQLITE"


@dataclass(frozen=True, slots=True)
class StorageCapability:
    kind: StorageKind
    durable: bool
    transactional: bool


CAPABILITIES = (
    StorageCapability(StorageKind.MEMORY, False, False),
    StorageCapability(StorageKind.JSONL, True, False),
    StorageCapability(StorageKind.SQLITE, True, True),
)


def choose_storage(*, durable: bool, transactional: bool) -> StorageCapability:
    candidates = [
        item
        for item in CAPABILITIES
        if (not durable or item.durable) and (not transactional or item.transactional)
    ]
    if not candidates:
        raise Refused("REFUSED_NO_STORAGE_CAPABILITY")
    return candidates[0]
