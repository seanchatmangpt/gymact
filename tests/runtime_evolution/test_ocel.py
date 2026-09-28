"""ocel wave falsifiers."""
from gymact.runtime_evolution.ocel.event import Event
def test_ocel_preserves_subject():
    before=Event("sha256:subject",0,("observed",)); after=before.evolve("challenger")
    assert after.subject==before.subject and after.epoch==1
    assert after.receipt()["wave"]=="ocel"
def test_ocel_refuses_empty_subject(): assert not Event("").admits()
