from gymact.explore_evidence_composition.engine import Qualification
from gymact.explore_evidence_composition.evidence import EvidenceKind, EvidenceNode
from gymact.explore_evidence_composition.interval import Interval
from gymact.explore_evidence_composition.methodology import REQUIRED
from gymact.explore_evidence_composition.replay import replay
from gymact.explore_evidence_composition.standing import Standing
from gymact.explore_evidence_composition.subject import Subject


def test_full_methodology_evidence_composes_without_crown_laundering() -> None:
    subject = Subject.parse("seanchatmangpt/gymact@" + "a" * 40 + "#" + "b" * 64)
    evidence = tuple(
        EvidenceNode(
            f"e{index}", subject, kind, 7, Interval(0.8, 0.95), f"impl{index}", f"model{index}", f"host{index}", 1.0
        )
        for index, kind in enumerate(EvidenceKind)
    )
    qualification = Qualification(
        subject,
        evidence,
        REQUIRED,
        (Standing.ALIVE, Standing.PARTIAL_ALIVE, Standing.ALIVE),
        "PARETO",
    )
    standing, receipt = qualification.evaluate()
    assert standing is Standing.PARTIAL_ALIVE
    assert receipt is not None
    assert replay(receipt, receipt.digest) == "REPLAY_MATCH"

    broken = Qualification(subject, evidence, REQUIRED, (Standing.ALIVE, Standing.BUILD_BROKEN), "MINIMAX")
    standing, receipt = broken.evaluate()
    assert standing is Standing.BUILD_BROKEN
    assert receipt is None
