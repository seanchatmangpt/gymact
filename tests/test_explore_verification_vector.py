import pytest
from gymact.explore_verification.evidence import Evidence
from gymact.explore_verification.subject import Subject
from gymact.explore_verification.vector import admit


def test_contradictory_axis_refuses():
    subject = Subject("o/r", "a" * 40)
    rows = [Evidence(subject, "repository", "PASS"), Evidence(subject, "repository", "FAIL")]
    with pytest.raises(ValueError, match="REFUSED_CONTRADICTORY_AXIS"):
        admit(rows, subject.sha)
