from dataclasses import dataclass
@dataclass(frozen=True)
class Strategy:
    name:str
    critical:tuple[str,...]=()
def candidates()->tuple[Strategy,...]:
    return (Strategy("ALL"),Strategy("QUORUM"),Strategy("CRITICAL_PATH"))
def complete(strategy:Strategy, states:dict[str,str])->bool:
    done={k for k,v in states.items() if v=="DISCHARGED"}
    if strategy.name=="ALL": return bool(states) and len(done)==len(states)
    if strategy.name=="QUORUM": return bool(states) and len(done) >= (len(states)//2+1)
    if strategy.name=="CRITICAL_PATH": return bool(strategy.critical) and set(strategy.critical)<=done
    raise ValueError("REFUSED[UNKNOWN_STRATEGY]")
