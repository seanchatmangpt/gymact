"""evidence wave falsifiers."""

from gymact.runtime_evolution.evidence.admission import Admission


def test_evidence_preserves_subject():
    before = Admission("sha256:subject", 0, ("observed",))
    after = before.evolve("challenger")
    assert after.subject == before.subject and after.epoch == 1
    assert after.receipt()["wave"] == "evidence"


def test_evidence_refuses_empty_subject():
    assert not Admission("").admits()
