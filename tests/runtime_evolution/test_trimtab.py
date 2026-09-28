"""trimtab wave falsifiers."""
from gymact.runtime_evolution.trimtab.context import Context
def test_trimtab_preserves_subject():
    before=Context("sha256:subject",0,("observed",)); after=before.evolve("challenger")
    assert after.subject==before.subject and after.epoch==1
    assert after.receipt()["wave"]=="trimtab"
def test_trimtab_refuses_empty_subject(): assert not Context("").admits()
