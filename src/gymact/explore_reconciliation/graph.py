from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Iterable


def reachable(edges: Iterable[tuple[str, str]], start: str, goal: str) -> bool:
    graph: dict[str, set[str]] = defaultdict(set)
    for source, target in edges:
        graph[source].add(target)
    queue = deque([start])
    seen = {start}
    while queue:
        node = queue.popleft()
        if node == goal:
            return True
        for target in sorted(graph[node]):
            if target not in seen:
                seen.add(target)
                queue.append(target)
    return False


def preserve_after_failure(
    edges: tuple[tuple[str, str], ...], failed: tuple[str, str]
) -> tuple[tuple[str, str], ...]:
    return tuple(edge for edge in edges if edge != failed)
