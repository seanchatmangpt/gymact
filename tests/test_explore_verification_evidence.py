import pytest
from gymact.explore_verification.evidence import Evidence
from gymact.explore_verification.subject import Subject


def test_invalid_outcome_refuses():
    subject = Subject("o/r", "a" * 40)
    assert Evidence(subject, "ci", "PASS").outcome == "PASS"
    with pytest.raises(ValueError, match="REFUSED_INVALID_OUTCOME"):
        Evidence(subject, "ci", "GREEN")
