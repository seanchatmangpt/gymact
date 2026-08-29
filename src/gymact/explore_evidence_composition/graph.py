from __future__ import annotations

from dataclasses import dataclass, field

from .evidence import EvidenceNode
from .refusal import RefusalCode, Refused


@dataclass(slots=True)
class EvidenceGraph:
    nodes: dict[str, EvidenceNode] = field(default_factory=dict)
    parents: dict[str, set[str]] = field(default_factory=dict)

    def add(self, node: EvidenceNode, parents: tuple[str, ...] = ()) -> None:
        if any(parent not in self.nodes for parent in parents):
            raise Refused(RefusalCode.UNSATISFIED_DEPENDENCY, "parent evidence missing")
        self.nodes[node.evidence_id] = node
        self.parents[node.evidence_id] = set(parents)
        self.topological_order()

    def topological_order(self) -> tuple[str, ...]:
        incoming = {key: set(value) for key, value in self.parents.items()}
        ready = sorted(key for key in self.nodes if not incoming.get(key))
        ordered: list[str] = []
        while ready:
            current = ready.pop(0)
            ordered.append(current)
            for child in sorted(self.nodes):
                if current in incoming.get(child, set()):
                    incoming[child].remove(current)
                    if not incoming[child] and child not in ordered and child not in ready:
                        ready.append(child)
                        ready.sort()
        if len(ordered) != len(self.nodes):
            raise Refused(RefusalCode.CYCLIC_EVIDENCE_GRAPH, "evidence graph contains a cycle")
        return tuple(ordered)
