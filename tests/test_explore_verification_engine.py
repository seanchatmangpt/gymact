from gymact.explore_verification.engine import qualify
from gymact.explore_verification.evidence import Evidence
from gymact.explore_verification.subject import Subject


def test_mixed_exact_head_cannot_launder_repository_failure():
    subject = Subject("seanchatmangpt/gymact", "0" * 40)
    rows = [
        Evidence(subject, "focused", "PASS"),
        Evidence(subject, "world", "PASS"),
        Evidence(subject, "repository", "FAIL"),
    ]
    result = qualify(rows, subject.sha)
    assert result["standing"] == "BUILD_BROKEN"
    assert result["actuation_performed"] is False
