from dataclasses import dataclass
from enum import Enum

class StoreKind(str,Enum): MEMORY="MEMORY"; JSONL="JSONL"; SQLITE="SQLITE"
@dataclass(frozen=True)
class StoreCandidate: kind:StoreKind; durable:bool; transactional:bool
def candidates():
    return (StoreCandidate(StoreKind.MEMORY,False,False),StoreCandidate(StoreKind.JSONL,True,False),StoreCandidate(StoreKind.SQLITE,True,True))
def select(*,durable=False,transactional=False):
    viable=[c for c in candidates() if (not durable or c.durable) and (not transactional or c.transactional)]
    return sorted(viable,key=lambda c:(c.transactional,c.durable,c.kind.value))[0]
