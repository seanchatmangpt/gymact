from dataclasses import dataclass
@dataclass(frozen=True)
class Candidate:
    id:str
    capabilities:frozenset[str]
    reversible:bool=True

def discover(candidates:list[Candidate], required:set[str])->tuple[Candidate,...]:
    return tuple(sorted((c for c in candidates if required <= c.capabilities), key=lambda c:c.id))
