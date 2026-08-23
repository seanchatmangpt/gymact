from fractions import Fraction
from gymact.explore_composition_selector_calibration import Calibration,CompositionMode,Selector,choose
from gymact.explore_composition_selector_calibration.pareto import Candidate,frontier

def test_selectors_and_frontier_do_not_collapse():
    cs=(Calibration(CompositionMode.CONSERVATIVE,4,Fraction(1),Fraction(3,5)),Calibration(CompositionMode.INDEPENDENT,4,Fraction(3,4),Fraction(1,5)))
    assert choose(cs,Selector.MAX_COVERAGE).mode=='CONSERVATIVE'
    assert choose(cs,Selector.MIN_WIDTH).mode=='INDEPENDENT'
    a=Candidate('a',Fraction(1),Fraction(1,2),Fraction(1,4),Fraction(1,2)); b=Candidate('b',Fraction(3,4),Fraction(3,4),Fraction(1,2),Fraction(3,4))
    assert frontier((a,b))==(a,)
