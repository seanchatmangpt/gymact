import unittest
from fractions import Fraction
from gymact.explore_calibration_regime.subject import Subject
from gymact.explore_calibration_regime.regime import CalibrationRegime
from gymact.explore_calibration_regime.engine import qualify_regime
from gymact.explore_calibration_regime.receipt import replay
from gymact.explore_calibration_regime.standing import Standing
class T(unittest.TestCase):
 def test_stable_then_drift(self):
  s=Subject("o/r","a"*40)
  stable=CalibrationRegime("source",1,"m1","STABLE")
  q=qualify_regime(subject=s,regime=stable,evidence_outcomes=("PASS",),drift=Fraction(1,10),cusum_alarm=False,transactional=True)
  self.assertEqual(q[0],Standing.PARTIAL_ALIVE); self.assertTrue(replay(q[3]))
  drift=CalibrationRegime("source",2,"m2","DRIFT")
  q2=qualify_regime(subject=s,regime=drift,evidence_outcomes=("PASS",),drift=Fraction(3,5),cusum_alarm=True)
  self.assertEqual(q2[0],Standing.REQUALIFYING)
