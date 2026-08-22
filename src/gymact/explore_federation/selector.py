from .pareto import frontier

def select(scores:dict[str,tuple[float,...]], blocked:set[str]=frozenset()):
    live={k:v for k,v in scores.items() if k not in blocked}
    if not live: raise ValueError("REFUSED_NO_VIABLE_CANDIDATE")
    f=frontier(live)
    return f[0], f
