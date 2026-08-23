import unittest
from datetime import UTC,datetime,timedelta
from gymact.explore_calibration_regime.window import CalibrationWindow
class T(unittest.TestCase):
 def test_half_open(self):
  a=datetime.now(UTC); b=a+timedelta(seconds=1); w=CalibrationWindow(a,b)
  self.assertTrue(w.contains(a)); self.assertFalse(w.contains(b))
