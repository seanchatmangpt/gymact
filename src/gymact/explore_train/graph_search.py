from collections import deque


def reachable(
    graph: dict[str, tuple[str, ...]], start: str, goal: str
) -> tuple[str, ...] | None:
    queue = deque([(start, (start,))])
    seen = {start}
    while queue:
        node, path = queue.popleft()
        if node == goal:
            return path
        for next_node in graph.get(node, ()):
            if next_node not in seen:
                seen.add(next_node)
                queue.append((next_node, (*path, next_node)))
    return None
