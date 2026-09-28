"""evolution wave falsifiers."""

from gymact.runtime_evolution.evolution.challenger import Challenger


def test_evolution_preserves_subject():
    before = Challenger("sha256:subject", 0, ("observed",))
    after = before.evolve("challenger")
    assert after.subject == before.subject and after.epoch == 1
    assert after.receipt()["wave"] == "evolution"


def test_evolution_refuses_empty_subject():
    assert not Challenger("").admits()
