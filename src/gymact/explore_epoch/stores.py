from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class StoreKind(str, Enum):
    MEMORY = "MEMORY"
    JSONL = "JSONL"
    SQLITE = "SQLITE"


@dataclass(frozen=True)
class StoreCandidate:
    kind: StoreKind
    durable: bool
    transactional: bool
    reversible: bool = True


def discover() -> tuple[StoreCandidate, ...]:
    return (
        StoreCandidate(StoreKind.MEMORY, False, False),
        StoreCandidate(StoreKind.JSONL, True, False),
        StoreCandidate(StoreKind.SQLITE, True, True),
    )
