import pytest

from gymact.explore_evidence_composition.authority import ActionClass, admit
from gymact.explore_evidence_composition.receipt import Receipt
from gymact.explore_evidence_composition.refusal import Refused
from gymact.explore_evidence_composition.replay import replay
from gymact.explore_evidence_composition.standing import Standing
from gymact.explore_evidence_composition.subject import Subject


def test_direct_do_refuses_and_receipt_replays() -> None:
    with pytest.raises(Refused):
        admit(ActionClass.DO)
    assert admit(ActionClass.DO, broker="BRCE") is ActionClass.DO
    subject = Subject.parse("seanchatmangpt/gymact@" + "a" * 40 + "#" + "b" * 64)
    receipt = Receipt(subject, Standing.PARTIAL_ALIVE, ("e2", "e1"), "PARETO")
    assert replay(receipt, receipt.digest) == "REPLAY_MATCH"
    with pytest.raises(Refused):
        replay(receipt, "0" * 64)
