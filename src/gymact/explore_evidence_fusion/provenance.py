from collections import defaultdict
class ProvenanceGraph:
    def __init__(self, edges=()):
        self.edges=tuple(edges)
        g=defaultdict(set)
        for a,b in self.edges:
            if a==b: raise ValueError("REFUSED_PROVENANCE_CYCLE")
            g[a].add(b); g.setdefault(b,set())
        temp=set(); perm=set()
        def visit(n):
            if n in temp: raise ValueError("REFUSED_PROVENANCE_CYCLE")
            if n in perm: return
            temp.add(n)
            for m in g[n]: visit(m)
            temp.remove(n); perm.add(n)
        for n in list(g): visit(n)
        self._g=g
    def derives(self,a,b):
        seen=set(); stack=[a]
        while stack:
            n=stack.pop()
            if n==b and n!=a: return True
            if n in seen: continue
            seen.add(n); stack.extend(self._g.get(n,()))
        return False
