from collections import defaultdict, deque


def canonical_toposort(nodes: set[str], edges: set[tuple[str, str]]) -> tuple[str, ...]:
    indegree = {n: 0 for n in nodes}
    outgoing: dict[str, set[str]] = defaultdict(set)
    for a, b in edges:
        outgoing[a].add(b)
        indegree[b] += 1
    ready = deque(sorted(n for n, d in indegree.items() if d == 0))
    order: list[str] = []
    while ready:
        n = ready.popleft()
        order.append(n)
        for m in sorted(outgoing[n]):
            indegree[m] -= 1
            if indegree[m] == 0:
                ready.append(m)
        ready = deque(sorted(ready))
    if len(order) != len(nodes):
        raise ValueError("cycle")
    return tuple(order)


def test_concurrent_events_normalize_deterministically() -> None:
    nodes = {"parse", "admit", "observe-a", "observe-b", "receipt"}
    edges = {("parse", "admit"), ("admit", "observe-a"), ("admit", "observe-b"), ("observe-a", "receipt"), ("observe-b", "receipt")}
    assert canonical_toposort(nodes, edges) == ("parse", "admit", "observe-a", "observe-b", "receipt")
