"""portability wave falsifiers."""

from gymact.runtime_evolution.portability.contract import Contract


def test_portability_preserves_subject():
    before = Contract("sha256:subject", 0, ("observed",))
    after = before.evolve("challenger")
    assert after.subject == before.subject and after.epoch == 1
    assert after.receipt()["wave"] == "portability"


def test_portability_refuses_empty_subject():
    assert not Contract("").admits()
