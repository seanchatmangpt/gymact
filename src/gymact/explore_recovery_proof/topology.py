from __future__ import annotations

from dataclasses import dataclass

from .subject import Refusal


@dataclass(frozen=True, slots=True)
class DependencyGraph:
    edges: dict[str, tuple[str, ...]]

    def __post_init__(self) -> None:
        nodes = set(self.edges)
        if any(dependency not in nodes for deps in self.edges.values() for dependency in deps):
            raise Refusal("REFUSED_UNKNOWN_DEPENDENCY")
        visiting: set[str] = set()
        done: set[str] = set()

        def visit(node: str) -> None:
            if node in visiting:
                raise Refusal("REFUSED_DEPENDENCY_CYCLE")
            if node in done:
                return
            visiting.add(node)
            for dependency in self.edges[node]:
                visit(dependency)
            visiting.remove(node)
            done.add(node)

        for node in sorted(nodes):
            visit(node)

    def blockers(self, standing: dict[str, str]) -> dict[str, tuple[str, ...]]:
        broken = {"BUILD_BROKEN", "BLOCKED"}
        result: dict[str, tuple[str, ...]] = {}
        for node in sorted(self.edges):
            seen: set[str] = set()
            stack = list(self.edges[node])
            while stack:
                dependency = stack.pop()
                if dependency in seen:
                    continue
                seen.add(dependency)
                stack.extend(self.edges[dependency])
            result[node] = tuple(sorted(dep for dep in seen if standing.get(dep) in broken))
        return result
