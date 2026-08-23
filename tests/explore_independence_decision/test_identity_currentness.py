from fractions import Fraction

import pytest

from gymact.explore_independence_decision import DecisionCalibration, Refused, Subject, current


def test_exact_subject_and_unique_current_calibration() -> None:
    subject = Subject.parse("seanchatmangpt/gymact", "a" * 40, "b" * 64)
    assert subject.key.endswith("#" + "b" * 64)
    old = DecisionCalibration(20, 1, 2, 1, "old")
    new = DecisionCalibration(40, 1, 1, 2, "new")
    assert current((old, new)) == new
    assert new.false_independent_rate == Fraction(1, 40)


def test_split_current_calibration_refuses() -> None:
    left = DecisionCalibration(20, 1, 1, 2, "left")
    right = DecisionCalibration(20, 1, 1, 2, "right")
    with pytest.raises(Refused, match="DIVERGENT_CURRENT_CALIBRATION"):
        current((left, right))
