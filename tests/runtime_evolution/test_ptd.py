"""ptd wave falsifiers."""
from gymact.runtime_evolution.ptd.epoch import Epoch
def test_ptd_preserves_subject():
    before=Epoch("sha256:subject",0,("observed",)); after=before.evolve("challenger")
    assert after.subject==before.subject and after.epoch==1
    assert after.receipt()["wave"]=="ptd"
def test_ptd_refuses_empty_subject(): assert not Epoch("").admits()
