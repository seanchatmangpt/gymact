"""doctrine wave falsifiers."""
from gymact.runtime_evolution.doctrine.intent import Intent
def test_doctrine_preserves_subject():
    before=Intent("sha256:subject",0,("observed",)); after=before.evolve("challenger")
    assert after.subject==before.subject and after.epoch==1
    assert after.receipt()["wave"]=="doctrine"
def test_doctrine_refuses_empty_subject(): assert not Intent("").admits()
