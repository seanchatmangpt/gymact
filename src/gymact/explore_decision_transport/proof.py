from dataclasses import dataclass

from .refusal import Refused


@dataclass(frozen=True, slots=True)
class Edge:
    parent: str
    child: str


def admit_acyclic(edges: list[Edge]) -> tuple[Edge, ...]:
    graph: dict[str, set[str]] = {}
    for edge in edges:
        graph.setdefault(edge.parent, set()).add(edge.child)
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> None:
        if node in visiting:
            raise Refused("CYCLIC_TRANSPORT_PROOF")
        if node in visited:
            return
        visiting.add(node)
        for child in graph.get(node, set()):
            visit(child)
        visiting.remove(node)
        visited.add(node)

    for node in sorted(graph):
        visit(node)
    return tuple(edges)
