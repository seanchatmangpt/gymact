from dataclasses import replace
from datetime import datetime, timezone

import pytest

from gymact.explore_supersession.epoch import Epoch
from gymact.explore_supersession.evidence import Evidence, Outcome
from gymact.explore_supersession.frontier import Frontier
from gymact.explore_supersession.receipt import make_receipt, replay
from gymact.explore_supersession.subject import Refusal, Subject


def test_receipt_replays_and_refuses_tamper():
    subject = Subject("seanchatmangpt/gymact", "a" * 40)
    row = Evidence(subject, Epoch(datetime.now(timezone.utc)), "ci", "focused", Outcome.PASS, "run-1")
    frontier = Frontier((row,), ())
    receipt = make_receipt(subject, frontier)
    assert replay(receipt, subject, frontier)
    with pytest.raises(Refusal, match="REFUSED_RECEIPT_MISMATCH"):
        replay(replace(receipt, standing="ALIVE"), subject, frontier)
