from __future__ import annotations

from collections import defaultdict, deque

from .identity import Refused
from .obligation import ObligationState


def propagate_blockers(edges: dict[str, set[str]], states: dict[str, ObligationState]) -> set[str]:
    indegree = defaultdict(int)
    children = defaultdict(set)
    nodes = set(states)
    for child, parents in edges.items():
        nodes.add(child)
        for parent in parents:
            children[parent].add(child)
            indegree[child] += 1
            nodes.add(parent)
    q = deque(sorted(n for n in nodes if indegree[n] == 0))
    seen: list[str] = []
    while q:
        node = q.popleft()
        seen.append(node)
        for child in sorted(children[node]):
            indegree[child] -= 1
            if indegree[child] == 0:
                q.append(child)
    if len(seen) != len(nodes):
        raise Refused("REFUSED_OBLIGATION_DEPENDENCY_CYCLE")
    blocked = set()
    for child, parents in edges.items():
        if any(states.get(parent) is not ObligationState.PASS for parent in parents):
            blocked.add(child)
    return blocked
