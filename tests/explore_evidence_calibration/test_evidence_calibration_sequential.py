import unittest
from gymact.explore_evidence_calibration.sequential import Decision,decide
from gymact.explore_evidence_calibration.strategies import FusionResult,FusionStrategy
class SequentialTests(unittest.TestCase):
    def test_under_calibration_cannot_promote(self):
        result=FusionResult(FusionStrategy.MINIMAX_UNDER_SUPPORT,9999,("s",),0); decision=decide(result)
        self.assertEqual(decision.decision,Decision.CONTINUE); self.assertEqual(decision.standing,"UNKNOWN")
    def test_failure_dominates(self):
        result=FusionResult(FusionStrategy.CALIBRATED_LOG_ODDS,9999,(),1); self.assertEqual(decide(result).standing,"BUILD_BROKEN")
