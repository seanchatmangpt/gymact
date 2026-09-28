"""graphlaw wave falsifiers."""

from gymact.runtime_evolution.graphlaw.invariant import Invariant


def test_graphlaw_preserves_subject():
    before = Invariant("sha256:subject", 0, ("observed",))
    after = before.evolve("challenger")
    assert after.subject == before.subject and after.epoch == 1
    assert after.receipt()["wave"] == "graphlaw"


def test_graphlaw_refuses_empty_subject():
    assert not Invariant("").admits()
