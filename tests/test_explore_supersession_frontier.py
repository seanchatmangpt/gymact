from datetime import UTC, datetime, timedelta

from gymact.explore_supersession.epoch import Epoch
from gymact.explore_supersession.evidence import Evidence, Outcome
from gymact.explore_supersession.frontier import resolve_frontier
from gymact.explore_supersession.subject import Subject
from gymact.explore_supersession.supersession import Supersession, SupersessionReason


def test_new_failure_supersedes_stale_green():
    subject = Subject("seanchatmangpt/gymact", "a" * 40)
    now = datetime.now(UTC)
    old = Evidence(subject, Epoch(now), "ci", "repository", Outcome.PASS, "run-old")
    new = Evidence(
        subject,
        Epoch(now + timedelta(seconds=1)),
        "ci",
        "repository",
        Outcome.FAIL,
        "run-new",
    )
    frontier = resolve_frontier(
        (old, new),
        (Supersession(old, new, SupersessionReason.NEW_RUN),),
    )
    assert frontier.current == (new,)
    assert frontier.historical == (old,)
    assert frontier.standing == "BUILD_BROKEN"
