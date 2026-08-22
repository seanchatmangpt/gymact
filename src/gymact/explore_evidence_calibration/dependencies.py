from __future__ import annotations
from .contracts import Refusal

def blockers(edges:dict[str,tuple[str,...]],standings:dict[str,str],root:str)->tuple[str,...]:
    visiting:set[str]=set(); visited:set[str]=set(); blocked:set[str]=set()
    def walk(node:str)->None:
        if node in visiting: raise Refusal("REFUSED_DEPENDENCY_CYCLE")
        if node in visited: return
        if node not in edges: raise Refusal("REFUSED_UNKNOWN_DEPENDENCY_NODE")
        visiting.add(node)
        for dep in edges[node]:
            if dep not in edges: raise Refusal("REFUSED_UNKNOWN_DEPENDENCY_NODE")
            walk(dep)
            if standings.get(dep,"UNKNOWN") in {"BUILD_BROKEN","BLOCKED"}: blocked.add(dep)
        visiting.remove(node); visited.add(node)
    walk(root); return tuple(sorted(blocked))
