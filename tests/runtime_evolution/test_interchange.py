"""interchange wave falsifiers."""

from gymact.runtime_evolution.interchange.edge import Edge


def test_interchange_preserves_subject():
    before = Edge("sha256:subject", 0, ("observed",))
    after = before.evolve("challenger")
    assert after.subject == before.subject and after.epoch == 1
    assert after.receipt()["wave"] == "interchange"


def test_interchange_refuses_empty_subject():
    assert not Edge("").admits()
