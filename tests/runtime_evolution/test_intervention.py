"""intervention wave falsifiers."""

from gymact.runtime_evolution.intervention.work_order import WorkOrder


def test_intervention_preserves_subject():
    before = WorkOrder("sha256:subject", 0, ("observed",))
    after = before.evolve("challenger")
    assert after.subject == before.subject and after.epoch == 1
    assert after.receipt()["wave"] == "intervention"


def test_intervention_refuses_empty_subject():
    assert not WorkOrder("").admits()
