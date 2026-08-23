import pytest

from gymact.explore_supersession.subject import Refusal, Subject


def test_exact_subject_required():
    with pytest.raises(Refusal, match="REFUSED_INEXACT_SUBJECT_SHA"):
        Subject("seanchatmangpt/gymact", "abc")
    subject = Subject("seanchatmangpt/gymact", "a" * 40)
    assert subject.identity.endswith("@" + "a" * 40)
