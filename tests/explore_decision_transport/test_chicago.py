from fractions import Fraction

import pytest

from gymact.explore_decision_transport.authority import ActionClass, admit
from gymact.explore_decision_transport.calibration import Calibration
from gymact.explore_decision_transport.qualification import qualify
from gymact.explore_decision_transport.receipt import Receipt
from gymact.explore_decision_transport.refusal import Refused
from gymact.explore_decision_transport.replay import replay
from gymact.explore_decision_transport.standing import Standing
from gymact.explore_decision_transport.subject import Subject


def test_transport_qualification_replay_and_failure_dominance() -> None:
    subject = Subject.parse("seanchatmangpt/gymact@860ce5ac422116ab05c69d79b4e194db0ed895fd")
    calibration = Calibration(1, "model-a", Fraction(1, 10), Fraction(1, 10), 100)
    qualified = qualify(calibration, [], min_support=50, max_gap=Fraction(1, 20))
    assert qualified.standing is Standing.PARTIAL_ALIVE
    receipt = Receipt(subject, "transport-a", qualified.standing)
    assert replay(receipt, receipt.digest()) == "REPLAY_MATCH"
    broken = qualify(calibration, [Standing.BUILD_BROKEN], min_support=50, max_gap=Fraction(1, 20))
    assert broken.standing is Standing.BUILD_BROKEN


def test_direct_do_and_receipt_tamper_refuse() -> None:
    with pytest.raises(Refused, match="UNRECEIPTED_ACTUATION"):
        admit(ActionClass.DO)
    subject = Subject.parse("seanchatmangpt/gymact@860ce5ac422116ab05c69d79b4e194db0ed895fd")
    receipt = Receipt(subject, "transport-a", Standing.PARTIAL_ALIVE)
    with pytest.raises(Refused, match="RECEIPT_DRIFT"):
        replay(receipt, "0" * 64)
