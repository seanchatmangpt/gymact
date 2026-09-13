import pytest

from gymact.explore_real_certificate_chain.authority import ActionClass, admit
from gymact.explore_real_certificate_chain.receipt import Receipt
from gymact.explore_real_certificate_chain.replay import replay


def test_ambient_do_refuses_and_brce_is_explicit() -> None:
    with pytest.raises(PermissionError, match="UNRECEIPTED_ACTUATION"):
        admit(ActionClass.DO)
    admit(ActionClass.DO, "BRCE")


def test_verify_receipt_replays_and_tamper_refuses() -> None:
    receipt = Receipt("subject", "certificate")
    replay(receipt, receipt.digest)
    with pytest.raises(ValueError, match="RECEIPT_DRIFT"):
        replay(receipt, "0" * 64)
