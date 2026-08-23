from dataclasses import dataclass
from enum import StrEnum

class StoreKind(StrEnum):
    MEMORY = "MEMORY"
    JSONL = "JSONL"
    SQLITE = "SQLITE"

@dataclass(frozen=True)
class StorageNeed:
    durable: bool = False
    transactional: bool = False

def select_store(need: StorageNeed) -> StoreKind:
    if need.transactional:
        return StoreKind.SQLITE
    if need.durable:
        return StoreKind.JSONL
    return StoreKind.MEMORY
