from __future__ import annotations

from dataclasses import dataclass

from .refusal import Refused
from .state import ObligationState
from .trajectory import ClosureEpoch


@dataclass(frozen=True, slots=True)
class DependencyGraph:
    edges: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        graph: dict[str, set[str]] = {}
        for parent, child in self.edges:
            graph.setdefault(parent, set()).add(child)
            graph.setdefault(child, set())
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node: str) -> None:
            if node in visiting:
                raise Refused("DEPENDENCY_CYCLE", node)
            if node in visited:
                return
            visiting.add(node)
            for child in graph.get(node, set()):
                visit(child)
            visiting.remove(node)
            visited.add(node)

        for node in graph:
            visit(node)

    def blocking_cut(self, epoch: ClosureEpoch) -> frozenset[str]:
        state = {item.key: item.state for item in epoch.obligations}
        bad = {
            key
            for key, value in state.items()
            if value in {ObligationState.FAIL, ObligationState.BLOCKED, ObligationState.REFUSED}
        }
        parents = {parent for parent, child in self.edges if child in bad and parent in state}
        return frozenset(bad | {parent for parent in parents if state[parent] != ObligationState.PASS})
