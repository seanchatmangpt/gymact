from dataclasses import dataclass

@dataclass(frozen=True)
class DependencyGraph:
    edges: dict[str, tuple[str, ...]]

    def __post_init__(self) -> None:
        nodes=set(self.edges)
        for src, deps in self.edges.items():
            if src in deps:
                raise ValueError("REFUSED_DEPENDENCY_CYCLE")
            missing=set(deps)-nodes
            if missing:
                raise ValueError("REFUSED_UNKNOWN_DEPENDENCY")
        self.topological_order()

    def topological_order(self) -> tuple[str, ...]:
        temporary=set(); permanent=set(); ordered=[]
        def visit(node):
            if node in permanent: return
            if node in temporary:
                raise ValueError("REFUSED_DEPENDENCY_CYCLE")
            temporary.add(node)
            for dep in sorted(self.edges[node]): visit(dep)
            temporary.remove(node); permanent.add(node); ordered.append(node)
        for node in sorted(self.edges): visit(node)
        return tuple(ordered)

    def closure(self, root: str) -> tuple[str, ...]:
        if root not in self.edges:
            raise ValueError("REFUSED_UNKNOWN_ROOT")
        seen=set()
        def walk(n):
            if n in seen: return
            seen.add(n)
            for d in self.edges[n]: walk(d)
        walk(root)
        return tuple(n for n in self.topological_order() if n in seen)
