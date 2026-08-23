from dataclasses import dataclass
from enum import StrEnum

from .refusal import Refused


class StorageKind(StrEnum):
    MEMORY = "MEMORY"
    JSONL = "JSONL"
    SQLITE = "SQLITE"


@dataclass(frozen=True, slots=True)
class StorageCandidate:
    kind: StorageKind
    durable: bool
    transactional: bool


def discover() -> tuple[StorageCandidate, ...]:
    return (
        StorageCandidate(StorageKind.MEMORY, durable=False, transactional=False),
        StorageCandidate(StorageKind.JSONL, durable=True, transactional=False),
        StorageCandidate(StorageKind.SQLITE, durable=True, transactional=True),
    )


def select(*, durable: bool = False, transactional: bool = False) -> StorageCandidate:
    for candidate in discover():
        if durable and not candidate.durable:
            continue
        if transactional and not candidate.transactional:
            continue
        return candidate
    raise Refused("REFUSED_NO_STORAGE_CAPABILITY")
