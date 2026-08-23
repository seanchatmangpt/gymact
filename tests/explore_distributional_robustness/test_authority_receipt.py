import pytest

from gymact.explore_distributional_robustness import Action, Receipt, ReceiptBody, admit_action


def test_direct_do_refuses_without_brce() -> None:
    with pytest.raises(ValueError, match="UNRECEIPTED_ACTUATION"):
        admit_action(Action.DO)
    assert admit_action(Action.DO, "BRCE") is Action.DO


def test_receipt_replay_detects_tamper() -> None:
    receipt = Receipt.issue(ReceiptBody("subject", "MIN_WORST", "PARTIAL_ALIVE"))
    assert receipt.replay()
    tampered = Receipt(ReceiptBody("subject", "MIN_NOMINAL", "PARTIAL_ALIVE"), receipt.digest)
    assert not tampered.replay()
