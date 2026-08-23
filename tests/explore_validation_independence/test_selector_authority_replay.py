from fractions import Fraction

import pytest

from gymact.explore_validation_independence import (
    ActionClass,
    Candidate,
    CompositionMode,
    Receipt,
    Refused,
    Standing,
    Strategy,
    Subject,
    admit,
    replay,
    select,
)


def test_selector_plurality_do_refusal_and_replay():
    candidates = (
        Candidate(
            CompositionMode.CONSERVATIVE,
            Fraction(1),
            Fraction(1, 2),
            Fraction(0),
            Fraction(0),
            1,
        ),
        Candidate(
            CompositionMode.INDEPENDENCE_QUALIFIED,
            Fraction(3, 4),
            Fraction(1, 4),
            Fraction(0),
            Fraction(1, 4),
            2,
        ),
    )
    assert select(candidates, Strategy.MAX_COVERAGE).mode is CompositionMode.CONSERVATIVE
    assert (
        select(candidates, Strategy.MIN_WIDTH).mode
        is CompositionMode.INDEPENDENCE_QUALIFIED
    )
    with pytest.raises(Refused, match="UNRECEIPTED_ACTUATION"):
        admit(ActionClass.DO)
    subject = Subject.parse("seanchatmangpt/gymact@" + "a" * 40 + "#" + "b" * 64)
    receipt = Receipt(
        subject,
        "MAX_COVERAGE",
        "CONSERVATIVE",
        Standing.PARTIAL_ALIVE,
        ("a", "b"),
    )
    assert replay(receipt, receipt.digest) == "REPLAY_MATCH"
