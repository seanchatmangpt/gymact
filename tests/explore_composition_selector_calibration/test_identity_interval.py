from fractions import Fraction
import pytest
from gymact.explore_composition_selector_calibration import Interval,Refused,Subject

def test_exact_subject_and_interval_falsifiers():
    s=Subject.parse('seanchatmangpt/gymact@'+'a'*40+'#'+'b'*64)
    assert s.repo=='seanchatmangpt/gymact'
    with pytest.raises(Refused): Subject.parse('gymact@short')
    with pytest.raises(Refused): Interval(Fraction(3,4),Fraction(1,2))
