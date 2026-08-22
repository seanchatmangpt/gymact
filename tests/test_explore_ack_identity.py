import pytest

from gymact.explore_ack_identity import Subject


def test_exact_identity_refuses_short_sha():
    with pytest.raises(ValueError, match="REFUSED_INVALID_SUBJECT_IDENTITY"):
        Subject("owner/repo", "abc", "producer")


def test_identity_key_is_exact():
    subject = Subject("o/r", "a" * 40, "consumer")
    assert subject.key == "o/r@" + "a" * 40 + ":consumer"
