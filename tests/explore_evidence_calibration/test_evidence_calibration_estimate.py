import unittest
from datetime import datetime,timezone
from fractions import Fraction
from gymact.explore_evidence_calibration.estimate import estimate
from gymact.explore_evidence_calibration.trials import CalibrationTrial
class EstimateTests(unittest.TestCase):
    def test_smoothed_estimate_and_support(self):
        now=datetime.now(timezone.utc)
        trials=tuple(CalibrationTrial("s",str(i),pred,actual,now) for i,(pred,actual) in enumerate([(1,1),(1,1),(1,0),(0,0)]))
        result=estimate("s",trials)
        self.assertEqual(result.support,4); self.assertEqual(result.true_positive_rate,Fraction(3,4)); self.assertEqual(result.false_positive_rate,Fraction(2,4)); self.assertTrue(result.calibrated)
