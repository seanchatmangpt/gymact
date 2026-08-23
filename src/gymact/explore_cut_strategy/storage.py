from dataclasses import dataclass
from enum import Enum

class StoreKind(str, Enum):
    MEMORY="MEMORY"
    JSONL="JSONL"
    SQLITE="SQLITE"

@dataclass(frozen=True)
class StoreCandidate:
    kind: StoreKind
    durable: bool
    transactional: bool

CANDIDATES=(
    StoreCandidate(StoreKind.MEMORY, False, False),
    StoreCandidate(StoreKind.JSONL, True, False),
    StoreCandidate(StoreKind.SQLITE, True, True),
)

def select_store(*, durable: bool=False, transactional: bool=False) -> StoreCandidate:
    viable=[c for c in CANDIDATES if (not durable or c.durable) and (not transactional or c.transactional)]
    if not viable:
        raise ValueError("REFUSED_NO_STORAGE_CANDIDATE")
    return viable[0]
