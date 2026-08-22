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

def discover_stores() -> tuple[StoreCandidate, ...]:
    return (
        StoreCandidate(StoreKind.MEMORY, False, False),
        StoreCandidate(StoreKind.JSONL, True, False),
        StoreCandidate(StoreKind.SQLITE, True, True),
    )

def select_store(require_durable: bool = False, require_transactional: bool = False) -> StoreCandidate:
    for candidate in discover_stores():
        if (not require_durable or candidate.durable) and (not require_transactional or candidate.transactional):
            return candidate
    raise RuntimeError("UNSUPPORTED_STORE_REQUIREMENTS")
