from __future__ import annotations

from dataclasses import dataclass

from .identity import Subject


@dataclass(frozen=True)
class DependencyGraph:
    edges: tuple[tuple[Subject, Subject], ...]

    def consumers(self, producer: Subject) -> tuple[Subject, ...]:
        adjacency: dict[Subject, list[Subject]] = {}
        for src, dst in self.edges:
            adjacency.setdefault(src, []).append(dst)
        seen: set[Subject] = set()
        active: set[Subject] = set()
        ordered: list[Subject] = []

        def visit(node: Subject) -> None:
            if node in active:
                raise ValueError("REFUSED_DEPENDENCY_CYCLE")
            if node in seen:
                return
            active.add(node)
            for child in sorted(adjacency.get(node, [])):
                visit(child)
                if child not in ordered:
                    ordered.append(child)
            active.remove(node)
            seen.add(node)

        visit(producer)
        return tuple(ordered)
