from dataclasses import dataclass
from enum import Enum

class Store(str, Enum):
    MEMORY = "MEMORY"
    JSONL = "JSONL"
    SQLITE = "SQLITE"

@dataclass(frozen=True, slots=True)
class PersistenceNeed:
    durable: bool = False
    transactional: bool = False

def candidates() -> tuple[Store, ...]:
    return (Store.MEMORY, Store.JSONL, Store.SQLITE)

def select(need: PersistenceNeed) -> Store:
    if need.transactional:
        return Store.SQLITE
    if need.durable:
        return Store.JSONL
    return Store.MEMORY
