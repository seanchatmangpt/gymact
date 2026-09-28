"""planning wave falsifiers."""
from gymact.runtime_evolution.planning.hddl import Hddl
def test_planning_preserves_subject():
    before=Hddl("sha256:subject",0,("observed",)); after=before.evolve("challenger")
    assert after.subject==before.subject and after.epoch==1
    assert after.receipt()["wave"]=="planning"
def test_planning_refuses_empty_subject(): assert not Hddl("").admits()
