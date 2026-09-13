import pytest

from gymact.explore_evidence_composition.dependency import Obligation, discharge
from gymact.explore_evidence_composition.evidence import EvidenceKind, EvidenceNode
from gymact.explore_evidence_composition.interval import Interval
from gymact.explore_evidence_composition.provenance import witness
from gymact.explore_evidence_composition.refusal import Refused
from gymact.explore_evidence_composition.subject import Subject


def mk(name: str, kind: EvidenceKind, impl: str, model: str, domain: str) -> EvidenceNode:
    subject = Subject.parse("seanchatmangpt/gymact@" + "a" * 40 + "#" + "b" * 64)
    return EvidenceNode(name, subject, kind, 3, Interval(0.8, 0.95), impl, model, domain)


def test_independence_requires_three_distinct_domains() -> None:
    left = mk("left", EvidenceKind.TRACE, "i1", "m1", "h1")
    right = mk("right", EvidenceKind.TRACE, "i2", "m2", "h2")
    assert witness(left, right).admitted
    with pytest.raises(Refused):
        witness(left, mk("alias", EvidenceKind.TRACE, "i1", "m2", "h2"))


def test_obligation_requires_each_declared_kind() -> None:
    trace = mk("trace", EvidenceKind.TRACE, "i1", "m1", "h1")
    obligation = Obligation(
        "runtime-correspondence", frozenset({EvidenceKind.TRACE, EvidenceKind.RUNTIME}), 3
    )
    with pytest.raises(Refused):
        discharge(obligation, (trace,))
