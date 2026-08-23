from dataclasses import dataclass
@dataclass(frozen=True, slots=True)
class Candidate:
    name:str; durable:bool; reversible:bool; network:bool=False
def discover()->tuple[Candidate,...]:
    return (Candidate('memory',False,True),Candidate('jsonl',True,True),Candidate('sqlite',True,True))
def admissible(cands): return tuple(c for c in cands if c.reversible and not c.network)
