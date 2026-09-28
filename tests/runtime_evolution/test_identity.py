"""identity wave falsifiers."""
from gymact.runtime_evolution.identity.subject import Subject
def test_identity_preserves_subject():
    before=Subject("sha256:subject",0,("observed",)); after=before.evolve("challenger")
    assert after.subject==before.subject and after.epoch==1
    assert after.receipt()["wave"]=="identity"
def test_identity_refuses_empty_subject(): assert not Subject("").admits()
