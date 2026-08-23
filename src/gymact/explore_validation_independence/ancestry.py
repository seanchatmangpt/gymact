from dataclasses import dataclass
from .evidence import Evidence
from .refusal import Refused

@dataclass(frozen=True)
class EvidenceGraph:
    nodes: tuple[Evidence, ...]

    def __post_init__(self) -> None:
        by_id = {node.evidence_id: node for node in self.nodes}
        if len(by_id) != len(self.nodes):
            raise Refused("DUPLICATE_EVIDENCE")
        for node in self.nodes:
            missing = set(node.parents) - set(by_id)
            if missing:
                raise Refused("MISSING_EVIDENCE_PARENT", ",".join(sorted(missing)))
        visiting: set[str] = set()
        visited: set[str] = set()
        def walk(node_id: str) -> None:
            if node_id in visiting:
                raise Refused("CYCLIC_EVIDENCE_GRAPH", node_id)
            if node_id in visited:
                return
            visiting.add(node_id)
            for parent in by_id[node_id].parents:
                walk(parent)
            visiting.remove(node_id)
            visited.add(node_id)
        for node_id in by_id:
            walk(node_id)

    def ancestors(self, evidence_id: str) -> frozenset[str]:
        by_id = {node.evidence_id: node for node in self.nodes}
        if evidence_id not in by_id:
            raise Refused("UNKNOWN_EVIDENCE", evidence_id)
        found: set[str] = set()
        stack = list(by_id[evidence_id].parents)
        while stack:
            current = stack.pop()
            if current in found:
                continue
            found.add(current)
            stack.extend(by_id[current].parents)
        return frozenset(found)
