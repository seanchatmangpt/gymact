from datetime import UTC, datetime, timedelta

import pytest

from gymact.explore_supersession.engine import qualify, require_authority
from gymact.explore_supersession.epoch import Epoch
from gymact.explore_supersession.evidence import Evidence, Outcome
from gymact.explore_supersession.receipt import replay
from gymact.explore_supersession.subject import Refusal, Subject
from gymact.explore_supersession.supersession import Supersession, SupersessionReason


def test_stale_green_new_failure_qualifies_without_do():
    subject = Subject("seanchatmangpt/gymact", "a" * 40)
    now = datetime.now(UTC)
    old = Evidence(subject, Epoch(now), "ci", "repository", Outcome.PASS, "old-green")
    new = Evidence(
        subject,
        Epoch(now + timedelta(seconds=1)),
        "ci",
        "repository",
        Outcome.FAIL,
        "new-red",
    )
    edge = Supersession(old, new, SupersessionReason.NEW_RUN)
    result = qualify(subject, [old, new], (edge,))
    assert result.frontier.standing == "BUILD_BROKEN"
    assert result.actuation_performed is False
    assert replay(result.receipt, subject, result.frontier)
    with pytest.raises(Refusal, match="REFUSED_UNRECEIPTED_ACTUATION"):
        require_authority("DO")
