import pytest

from gymact.explore_verification.receipt import make, replay


def test_receipt_replay_and_tamper_refusal():
    receipt = make("a" * 40, "PARTIAL_ALIVE", {"focused": "PASS"})
    assert replay(receipt)
    receipt["body"]["standing"] = "ALIVE"
    with pytest.raises(ValueError, match="REFUSED_RECEIPT_MISMATCH"):
        replay(receipt)
