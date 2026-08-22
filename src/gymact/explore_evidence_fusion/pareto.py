def pareto_frontier(decisions):
    def vec(d): return tuple(float(x) for x in d.score)
    out=[]
    for d in decisions:
        v=vec(d); dominated=False
        for e in decisions:
            if e is d: continue
            w=vec(e)
            if len(v)==len(w) and all(a>=b for a,b in zip(w,v)) and any(a>b for a,b in zip(w,v)):
                dominated=True; break
        if not dominated: out.append(d)
    return tuple(sorted(out,key=lambda d:d.strategy.value))
