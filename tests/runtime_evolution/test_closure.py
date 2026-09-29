"""closure wave falsifiers."""

from gymact.runtime_evolution.closure.coordinator import Coordinator


def test_closure_preserves_subject():
    before = Coordinator("sha256:subject", 0, ("observed",))
    after = before.evolve("challenger")
    assert after.subject == before.subject and after.epoch == 1
    assert after.receipt()["wave"] == "closure"


def test_closure_refuses_empty_subject():
    assert not Coordinator("").admits()
