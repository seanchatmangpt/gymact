from dataclasses import dataclass
from enum import StrEnum


class StorageKind(StrEnum):
    MEMORY = "MEMORY"
    JSONL = "JSONL"
    SQLITE = "SQLITE"


@dataclass(frozen=True)
class StorageNeed:
    durable: bool = False
    transactional: bool = False


def select_storage(need: StorageNeed) -> StorageKind:
    if need.transactional:
        return StorageKind.SQLITE
    if need.durable:
        return StorageKind.JSONL
    return StorageKind.MEMORY


def discover_storage() -> tuple[StorageKind, ...]:
    return tuple(StorageKind)
