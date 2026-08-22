def topo(edges:dict[str,set[str]])->tuple[str,...]:
    temp=set(); done=set(); out=[]
    def visit(n):
        if n in temp: raise ValueError("REFUSED_DEPENDENCY_CYCLE")
        if n in done:return
        temp.add(n)
        for d in sorted(edges.get(n,set())): visit(d)
        temp.remove(n); done.add(n); out.append(n)
    for n in sorted(edges): visit(n)
    return tuple(out)
