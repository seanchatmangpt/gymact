from fractions import Fraction
import pytest
from gymact.explore_kantorovich_ambiguity import FiniteMeasure, Refused, Subject

def test_exact_subject_and_normalized_measure():
    s = Subject("seanchatmangpt/gymact", "f" * 40, "pi:k")
    assert s.semantic == "pi:k"
    m = FiniteMeasure.from_mapping({"a": 2, "b": 1})
    assert m.probability("a") == Fraction(2, 3)
    assert sum(dict(m.mass).values(), Fraction()) == 1

def test_short_sha_and_zero_mass_refuse():
    with pytest.raises(Refused, match="INVALID_SUBJECT_SHA"):
        Subject("seanchatmangpt/gymact", "f" * 7, "pi:k")
    with pytest.raises(Refused, match="ZERO_TOTAL_MASS"):
        FiniteMeasure.from_mapping({"a": 0})
