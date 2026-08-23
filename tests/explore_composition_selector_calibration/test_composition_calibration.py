from fractions import Fraction
from gymact.explore_composition_selector_calibration import CompositionCase,CompositionMode,Interval
from gymact.explore_composition_selector_calibration.calibration import Calibration

def test_mode_calibration_is_noncollapsed():
    cases=(CompositionCase('c1',CompositionMode.CONSERVATIVE,Interval(Fraction(1,4),Fraction(3,4)),Fraction(1,2)),CompositionCase('i1',CompositionMode.INDEPENDENT,Interval(Fraction(2,5),Fraction(3,5)),Fraction(9,10)))
    c=Calibration.from_cases(CompositionMode.CONSERVATIVE,cases); i=Calibration.from_cases(CompositionMode.INDEPENDENT,cases)
    assert c.coverage==1 and i.coverage==0 and c.mean_width!=i.mean_width
