import pytest

from gymact.explore_kantorovich_duality.receipt import Receipt
from gymact.explore_kantorovich_duality.replay import replay
from gymact.explore_kantorovich_duality.standing import Standing


def test_receipt_replays_exactly() -> None:
    receipt = Receipt("subject", "3", Standing.PARTIAL_ALIVE)
    replay(receipt, receipt.digest())


def test_digest_drift_refuses() -> None:
    receipt = Receipt("subject", "3", Standing.PARTIAL_ALIVE)
    with pytest.raises(ValueError, match="RECEIPT_DRIFT"):
        replay(receipt, "0" * 64)


def test_receipt_cannot_report_actuation() -> None:
    receipt = Receipt("subject", "3", Standing.PARTIAL_ALIVE, actuation_performed=True)
    with pytest.raises(ValueError, match="RECEIPT_ACTUATION"):
        receipt.digest()
