from dataclasses import dataclass
from .errors import Refused
from .epoch import ClosureEpoch
from .obligation import State

@dataclass(frozen=True)
class DependencyGraph:
    parents: dict[str, tuple[str, ...]]

    def __post_init__(self) -> None:
        seen: set[str] = set()
        active: set[str] = set()
        def visit(node: str) -> None:
            if node in active:
                raise Refused("REFUSED_DEPENDENCY_CYCLE", node)
            if node in seen:
                return
            active.add(node)
            for parent in self.parents.get(node, ()):
                visit(parent)
            active.remove(node)
            seen.add(node)
        for node in self.parents:
            visit(node)

    def blocking_cut(self, epoch: ClosureEpoch) -> tuple[str, ...]:
        states = {o.key: o.state for o in epoch.obligations}
        cut: set[str] = set()
        for child, parents in self.parents.items():
            if states.get(child) == State.PASS:
                stack = list(parents)
                visited: set[str] = set()
                while stack:
                    parent = stack.pop()
                    if parent in visited:
                        continue
                    visited.add(parent)
                    if states.get(parent, State.UNKNOWN) != State.PASS:
                        cut.add(parent)
                    stack.extend(self.parents.get(parent, ()))
        return tuple(sorted(cut))
