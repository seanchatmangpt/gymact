import pytest

from gymact.explore_transport_invariance import (
    Action,
    Refusal,
    Subject,
    issue,
    replay,
    require_authority,
)


def test_direct_do_refuses_without_brce() -> None:
    with pytest.raises(Refusal):
        require_authority(Action.DO)


def test_no_actuation_receipt_replays() -> None:
    subject = Subject("seanchatmangpt/gymact", "c" * 40, "semantic-digest-0002")
    receipt = issue(subject, "MINIMAX", "PARTIAL_ALIVE")
    assert receipt.actuation_performed is False
    assert replay(receipt)
