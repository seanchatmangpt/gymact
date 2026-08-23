from dataclasses import dataclass
from enum import StrEnum


class StorageKind(StrEnum):
    MEMORY = "MEMORY"
    JSONL = "JSONL"
    SQLITE = "SQLITE"


@dataclass(frozen=True, slots=True)
class StorageCapability:
    kind: StorageKind
    durable: bool
    transactional: bool


CANDIDATES = (
    StorageCapability(StorageKind.MEMORY, False, False),
    StorageCapability(StorageKind.JSONL, True, False),
    StorageCapability(StorageKind.SQLITE, True, True),
)


def select_storage(*, durable: bool, transactional: bool) -> StorageCapability | None:
    def admits(candidate: StorageCapability) -> bool:
        return (not durable or candidate.durable) and (not transactional or candidate.transactional)

    return next((candidate for candidate in CANDIDATES if admits(candidate)), None)
