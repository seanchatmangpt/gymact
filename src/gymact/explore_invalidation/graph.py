from __future__ import annotations
from collections import defaultdict, deque
from .model import Binding, Refusal, Subject

class DependencyGraph:
    def __init__(self, bindings: list[Binding]) -> None:
        self.bindings = tuple(bindings)
        self._out: dict[Subject, list[Binding]] = defaultdict(list)
        for binding in bindings:
            self._out[binding.producer].append(binding)
        self._assert_acyclic()
    def _assert_acyclic(self) -> None:
        indegree: dict[Subject, int] = defaultdict(int)
        nodes: set[Subject] = set()
        for b in self.bindings:
            nodes |= {b.producer, b.consumer}
            indegree[b.consumer] += 1
            indegree.setdefault(b.producer, 0)
        queue = deque(sorted((n for n in nodes if indegree[n] == 0), key=lambda n: n.identity))
        seen = 0
        while queue:
            node = queue.popleft(); seen += 1
            for b in self._out.get(node, []):
                indegree[b.consumer] -= 1
                if indegree[b.consumer] == 0:
                    queue.append(b.consumer)
        if seen != len(nodes):
            raise Refusal("REFUSED_DEPENDENCY_CYCLE")
    def outgoing(self, subject: Subject) -> tuple[Binding, ...]:
        return tuple(sorted(self._out.get(subject, []), key=lambda b: b.binding_id))
