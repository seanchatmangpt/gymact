from __future__ import annotations
from dataclasses import dataclass
from enum import Enum

class StoreKind(str,Enum): MEMORY="MEMORY"; JSONL="JSONL"; SQLITE="SQLITE"
@dataclass(frozen=True)
class StoreCandidate:
    kind: StoreKind; durable: bool; transactional: bool

def candidates()->tuple[StoreCandidate,...]:
    return (StoreCandidate(StoreKind.MEMORY,False,False),StoreCandidate(StoreKind.JSONL,True,False),StoreCandidate(StoreKind.SQLITE,True,True))

def select(*,durable:bool,transactional:bool)->StoreCandidate:
    viable=[c for c in candidates() if (not durable or c.durable) and (not transactional or c.transactional)]
    return min(viable,key=lambda c:(c.durable,c.transactional,c.kind.value))
