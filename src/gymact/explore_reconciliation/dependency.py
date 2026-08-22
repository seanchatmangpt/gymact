from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DependencyEdge:
    source: str
    target: str


def topo_order(nodes: Iterable[str], edges: Iterable[DependencyEdge]) -> tuple[str, ...]:
    node_set = set(nodes)
    incoming = {node: 0 for node in node_set}
    outgoing: dict[str, set[str]] = defaultdict(set)
    for edge in edges:
        if edge.source not in node_set or edge.target not in node_set:
            raise ValueError("REFUSED_DANGLING_DEPENDENCY_EDGE")
        if edge.target not in outgoing[edge.source]:
            outgoing[edge.source].add(edge.target)
            incoming[edge.target] += 1
    ready = sorted(node for node, count in incoming.items() if count == 0)
    ordered: list[str] = []
    while ready:
        node = ready.pop(0)
        ordered.append(node)
        for target in sorted(outgoing[node]):
            incoming[target] -= 1
            if incoming[target] == 0:
                ready.append(target)
                ready.sort()
    if len(ordered) != len(node_set):
        raise ValueError("REFUSED_DEPENDENCY_CYCLE")
    return tuple(ordered)
