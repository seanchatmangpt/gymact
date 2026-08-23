from fractions import Fraction

import pytest

from gymact.explore_kantorovich_duality import DualityRefusal, FiniteMeasure, Subject


def test_exact_subject_and_measure_normalization() -> None:
    subject = Subject.admit("seanchatmangpt/gymact", "a" * 40, "ot-duality")
    measure = FiniteMeasure.normalize({"a": 2, "b": 1})
    assert subject.semantic == "ot-duality"
    assert measure.mass == {"a": Fraction(2, 3), "b": Fraction(1, 3)}


def test_inexact_subject_refuses() -> None:
    with pytest.raises(DualityRefusal, match="INVALID_SUBJECT"):
        Subject.admit("gymact", "abc", "")
