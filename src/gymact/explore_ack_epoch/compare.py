from .strategy import Strategy, complete
def compare(strategies:tuple[Strategy,...], states:dict[str,str])->dict[str,bool]:
    return {s.name:complete(s,states) for s in strategies}
def pareto_completion(results:dict[str,bool])->tuple[str,...]:
    return tuple(sorted(k for k,v in results.items() if v))
