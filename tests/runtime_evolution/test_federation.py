"""federation wave falsifiers."""

from gymact.runtime_evolution.federation.source import Source


def test_federation_preserves_subject():
    before = Source("sha256:subject", 0, ("observed",))
    after = before.evolve("challenger")
    assert after.subject == before.subject and after.epoch == 1
    assert after.receipt()["wave"] == "federation"


def test_federation_refuses_empty_subject():
    assert not Source("").admits()
