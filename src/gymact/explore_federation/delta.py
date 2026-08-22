from dataclasses import dataclass
@dataclass(frozen=True)
class Delta:
    key:str
    before:object
    after:object
    changed:bool

def diff(before:dict, after:dict)->tuple[Delta,...]:
    keys=sorted(set(before)|set(after))
    return tuple(Delta(k,before.get(k),after.get(k),before.get(k)!=after.get(k)) for k in keys)
