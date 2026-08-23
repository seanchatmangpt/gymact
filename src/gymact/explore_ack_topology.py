from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .explore_ack_identity import Subject


@dataclass(frozen=True)
class DependencyGraph:
    consumers: tuple[Subject, ...]
    edges: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        keys = {c.key for c in self.consumers}
        if len(keys) != len(self.consumers):
            raise ValueError("REFUSED_DUPLICATE_CONSUMER")
        graph: dict[str, list[str]] = defaultdict(list)
        for parent, child in self.edges:
            if parent not in keys or child not in keys:
                raise ValueError("REFUSED_UNKNOWN_DEPENDENCY_NODE")
            graph[parent].append(child)

        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node: str) -> None:
            if node in visiting:
                raise ValueError("REFUSED_DEPENDENCY_CYCLE")
            if node in visited:
                return
            visiting.add(node)
            for nxt in graph[node]:
                visit(nxt)
            visiting.remove(node)
            visited.add(node)

        for key in keys:
            visit(key)

    def descendants(self, root: Subject) -> tuple[Subject, ...]:
        by_key = {c.key: c for c in self.consumers}
        children: dict[str, list[str]] = defaultdict(list)
        for parent, child in self.edges:
            children[parent].append(child)
        seen: set[str] = set()
        stack = [root.key]
        while stack:
            cur = stack.pop()
            for child in children[cur]:
                if child not in seen:
                    seen.add(child)
                    stack.append(child)
        return tuple(sorted((by_key[k] for k in seen), key=lambda s: s.key))
