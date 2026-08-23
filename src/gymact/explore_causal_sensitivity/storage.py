from dataclasses import dataclass
from enum import StrEnum


class StorageKind(StrEnum):
    MEMORY = "MEMORY"
    JSONL = "JSONL"
    SQLITE = "SQLITE"


@dataclass(frozen=True)
class StorageRequest:
    transactional: bool = False
    append_only: bool = False


def admissible_storage(request: StorageRequest) -> tuple[StorageKind, ...]:
    if request.transactional:
        return (StorageKind.SQLITE,)
    if request.append_only:
        return (StorageKind.JSONL, StorageKind.SQLITE)
    return (StorageKind.MEMORY, StorageKind.JSONL, StorageKind.SQLITE)
