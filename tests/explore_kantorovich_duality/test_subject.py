import pytest

from gymact.explore_kantorovich_duality.subject import Subject


def test_exact_subject_required() -> None:
    with pytest.raises(ValueError, match="INVALID_SUBJECT"):
        Subject("seanchatmangpt/gymact", "abc", "kantorovich-duality")


def test_exact_subject_identity() -> None:
    subject = Subject("seanchatmangpt/gymact", "4" * 40, "kantorovich-duality")
    assert subject.identity.endswith("#kantorovich-duality")
