from dataclasses import dataclass
@dataclass(frozen=True)
class Store:
    name:str; durable:bool; transactional:bool
CANDIDATES=(Store("MEMORY",False,False),Store("JSONL",True,False),Store("SQLITE",True,True))
def discover(): return CANDIDATES
def select(*,durable=False,transactional=False):
    viable=[s for s in CANDIDATES if (not durable or s.durable) and (not transactional or s.transactional)]
    if not viable: raise ValueError("REFUSED_NO_STORAGE_CANDIDATE")
    return viable[0]
