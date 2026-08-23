from fractions import Fraction

import pytest

from gymact.explore_transport_invariance import Calibration, Refusal, current


def test_unique_latest_calibration_wins() -> None:
    old = Calibration(10, Fraction(1, 5), 1, "calibration-digest-old")
    new = Calibration(20, Fraction(1, 10), 2, "calibration-digest-new")
    assert current((old, new)) == new


def test_split_latest_generation_refuses() -> None:
    a = Calibration(20, Fraction(1, 10), 2, "calibration-digest-a00")
    b = Calibration(20, Fraction(1, 10), 2, "calibration-digest-b00")
    with pytest.raises(Refusal):
        current((a, b))
