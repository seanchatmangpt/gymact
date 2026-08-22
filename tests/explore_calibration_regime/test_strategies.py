import unittest
from fractions import Fraction
from gymact.explore_calibration_regime.strategies import evaluate
class T(unittest.TestCase):
 def test_distinct(self):
  a=evaluate("WINDOW_L1",drift=Fraction(3,5),cusum_alarm=False,support=8)
  b=evaluate("PREQUENTIAL_CUSUM",drift=Fraction(3,5),cusum_alarm=False,support=8)
  self.assertNotEqual(a.accept,b.accept)
