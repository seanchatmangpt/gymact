from gymact.explore_ack_comparator import Result
from gymact.explore_ack_receipt import make_receipt, replay


def test_receipt_replay_detects_mutated_evidence():
    receipt = make_receipt(
        "o/r@" + "a" * 40,
        "evt",
        Result(True, True, 1, 1, "ALL"),
        b"evidence",
    )
    assert replay(receipt, b"evidence")
    assert not replay(receipt, b"tampered")
