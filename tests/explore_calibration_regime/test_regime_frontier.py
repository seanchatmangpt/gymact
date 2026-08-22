import unittest
from gymact.explore_calibration_regime.regime import CalibrationRegime
from gymact.explore_calibration_regime.frontier import current_frontier
from gymact.explore_calibration_regime.refusal import Refusal
class T(unittest.TestCase):
 def test_divergent(self):
  a=CalibrationRegime("s",1,"a","STABLE"); b=CalibrationRegime("s",1,"b","DRIFT")
  with self.assertRaises(Refusal): current_frontier([a,b])
