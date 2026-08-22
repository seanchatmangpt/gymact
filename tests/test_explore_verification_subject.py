import pytest
from gymact.explore_verification.subject import Subject


def test_exact_subject_and_short_sha_refusal():
    assert Subject("o/r", "a" * 40).sha == "a" * 40
    with pytest.raises(ValueError, match="REFUSED_INEXACT_SUBJECT"):
        Subject("o/r", "abc")
