from collections import deque


def reachable(graph: dict[str, tuple[str, ...]], start: str, goal: str) -> tuple[str, ...] | None:
    q = deque([(start, (start,))]); seen = {start}
    while q:
        node, path = q.popleft()
        if node == goal: return path
        for nxt in graph.get(node, ()):
            if nxt not in seen:
                seen.add(nxt); q.append((nxt, path + (nxt,)))
    return None
