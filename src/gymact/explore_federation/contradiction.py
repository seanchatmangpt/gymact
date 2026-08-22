from dataclasses import dataclass
@dataclass(frozen=True)
class Contradiction:
    key:str
    outcomes:tuple[str,...]
def detect(rows:list[tuple[str,str]])->tuple[Contradiction,...]:
    by={}
    for k,o in rows: by.setdefault(k,set()).add(o)
    return tuple(Contradiction(k,tuple(sorted(v))) for k,v in sorted(by.items()) if len(v)>1)
