from dataclasses import dataclass
@dataclass(frozen=True)
class StoreCandidate:
    name:str
    durable:bool
    transactional:bool
def stores():
    return (StoreCandidate("MEMORY",False,False),StoreCandidate("JSONL",True,False),StoreCandidate("SQLITE",True,True))
def select_store(*,durable=False,transactional=False)->StoreCandidate:
    viable=[s for s in stores() if (not durable or s.durable) and (not transactional or s.transactional)]
    if not viable: raise ValueError("REFUSED[NO_STORE_CANDIDATE]")
    return viable[0]
