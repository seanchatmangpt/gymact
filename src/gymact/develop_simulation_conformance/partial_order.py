from __future__ import annotations

from collections import defaultdict, deque


def normalize(nodes: list[str], edges: list[tuple[str, str]]) -> tuple[str, ...]:
    incoming = {node: 0 for node in nodes}
    outgoing: dict[str, list[str]] = defaultdict(list)
    for left, right in edges:
        if left not in incoming or right not in incoming:
            raise ValueError("REFUSED[UNKNOWN_TRACE_NODE]")
        incoming[right] += 1
        outgoing[left].append(right)
    ready = deque(sorted(node for node, degree in incoming.items() if degree == 0))
    ordered: list[str] = []
    while ready:
        node = ready.popleft()
        ordered.append(node)
        for nxt in sorted(outgoing[node]):
            incoming[nxt] -= 1
            if incoming[nxt] == 0:
                ready.append(nxt)
    if len(ordered) != len(nodes):
        raise ValueError("REFUSED[CYCLIC_TRACE]")
    return tuple(ordered)
