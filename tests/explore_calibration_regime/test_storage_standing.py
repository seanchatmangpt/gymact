import unittest
from gymact.explore_calibration_regime.storage import candidates,select,StoreKind
from gymact.explore_calibration_regime.standing import resolve,Standing
class T(unittest.TestCase):
 def test_reversible_and_dominant(self):
  self.assertEqual(len(candidates()),3); self.assertEqual(select(durable=True,transactional=True).kind,StoreKind.SQLITE)
  self.assertEqual(resolve(regime_state="STABLE",evidence_outcomes=("PASS","FAIL")),Standing.BUILD_BROKEN)
