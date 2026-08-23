import pytest

from gymact.explore_relation_selection_calibration.authority import ActionClass, admit_action
from gymact.explore_relation_selection_calibration.errors import Refused
from gymact.explore_relation_selection_calibration.receipt import Receipt
from gymact.explore_relation_selection_calibration.replay import replay
from gymact.explore_relation_selection_calibration.standing import Standing


def test_direct_do_refuses() -> None:
    with pytest.raises(Refused, match="UNRECEIPTED_ACTUATION"):
        admit_action(ActionClass.DO)


def test_receipt_replay_is_deterministic() -> None:
    receipt = Receipt("seanchatmangpt/gymact@" + "7" * 40, 3, ("EXACT",), Standing.PARTIAL_ALIVE)
    assert replay(receipt, receipt.digest()) == "REPLAY_MATCH"
    with pytest.raises(Refused, match="REPLAY_DIGEST_MISMATCH"):
        replay(receipt, "0" * 64)
