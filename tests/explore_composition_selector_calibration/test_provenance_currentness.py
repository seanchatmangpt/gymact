from fractions import Fraction
import pytest
from gymact.explore_composition_selector_calibration import Calibration,CalibrationVersion,CompositionMode,Refused,current_frontier
from gymact.explore_composition_selector_calibration.provenance import Provenance,require_independent

def test_provenance_and_frontier_refusals():
    p=Provenance('impl','model','domain')
    with pytest.raises(Refused): require_independent(p,p)
    c=Calibration(CompositionMode.CONSERVATIVE,3,Fraction(1),Fraction(1,2))
    with pytest.raises(Refused): current_frontier((CalibrationVersion(2,'a',c),CalibrationVersion(2,'b',c)))
