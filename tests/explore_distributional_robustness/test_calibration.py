from fractions import Fraction

import pytest

from gymact.explore_distributional_robustness import Calibration, current


def test_current_calibration_selects_latest_generation() -> None:
    old = Calibration(1, "old", 10, Fraction(1, 10), Fraction(1, 2))
    new = Calibration(2, "new", 20, Fraction(1, 20), Fraction(1, 3))
    assert current((old, new)) == new


def test_split_current_generation_refuses() -> None:
    left = Calibration(2, "a", 20, Fraction(1, 20), Fraction(1, 3))
    right = Calibration(2, "b", 20, Fraction(1, 20), Fraction(1, 3))
    with pytest.raises(ValueError, match="DIVERGENT_CURRENT_CALIBRATION"):
        current((left, right))
