import unittest
from gymact.explore_calibration_regime.receipt import issue,replay,Receipt
from gymact.explore_calibration_regime.authority import require,ActionClass
from gymact.explore_calibration_regime.refusal import Refusal
class T(unittest.TestCase):
 def test_tamper_and_do(self):
  r=issue({"x":1}); self.assertTrue(replay(r)); self.assertFalse(replay(Receipt({**r.payload,"x":2},r.digest)))
  with self.assertRaises(Refusal): require(ActionClass.DO)
