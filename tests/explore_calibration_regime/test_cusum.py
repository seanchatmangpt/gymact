import unittest
from gymact.explore_calibration_regime.cusum import detect
class T(unittest.TestCase):
 def test_shift_alarm(self):
  self.assertFalse(detect([False]*8).alarm)
  self.assertTrue(detect([True]*4).alarm)
