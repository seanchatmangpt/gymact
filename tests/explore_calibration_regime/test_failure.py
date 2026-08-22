import unittest
from gymact.explore_calibration_regime.failure import inject_regime_shift
class T(unittest.TestCase):
 def test_seeded(self):
  x=(True,False,True,False)
  self.assertEqual(inject_regime_shift(x,seed=7,probability_ppm=500000),inject_regime_shift(x,seed=7,probability_ppm=500000))
