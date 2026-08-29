import pytest

from gymact.explore_evidence_composition.currentness import current_frontier, require_current
from gymact.explore_evidence_composition.evidence import EvidenceKind, EvidenceNode
from gymact.explore_evidence_composition.graph import EvidenceGraph
from gymact.explore_evidence_composition.interval import Interval
from gymact.explore_evidence_composition.refusal import Refused
from gymact.explore_evidence_composition.subject import Subject


def node(name: str, generation: int, impl: str = "i1") -> EvidenceNode:
    subject = Subject.parse("seanchatmangpt/gymact@" + "a" * 40 + "#" + "b" * 64)
    return EvidenceNode(name, subject, EvidenceKind.TRACE, generation, Interval(0.8, 0.9), impl, "m1", "host-a")


def test_graph_orders_dependencies_and_frontier_rejects_stale() -> None:
    graph = EvidenceGraph()
    old = node("old", 1)
    fresh = node("fresh", 2)
    graph.add(old)
    graph.add(fresh, ("old",))
    assert graph.topological_order() == ("old", "fresh")
    frontier = current_frontier((old, fresh))
    assert frontier == (fresh,)
    with pytest.raises(Refused):
        require_current(old, frontier)


def test_divergent_latest_identity_refuses() -> None:
    with pytest.raises(Refused):
        current_frontier((node("a", 2, "i1"), node("b", 2, "i2")))
