from dataclasses import dataclass


@dataclass(frozen=True)
class SemanticEdge:
    subject: str
    predicate: str
    object: str


def canonical_edges(edges: list[SemanticEdge]) -> tuple[SemanticEdge, ...]:
    return tuple(sorted(set(edges), key=lambda edge: (edge.subject, edge.predicate, edge.object)))
