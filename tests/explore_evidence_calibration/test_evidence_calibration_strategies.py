import unittest
from datetime import datetime,timezone
from gymact.explore_evidence_calibration.contracts import Subject
from gymact.explore_evidence_calibration.estimate import estimate
from gymact.explore_evidence_calibration.strategies import FusionStrategy,evaluate
from gymact.explore_evidence_calibration.trials import CalibrationTrial
from gymact.explore_evidence_calibration.witness import CurrentWitness
class StrategyTests(unittest.TestCase):
    def test_strategies_remain_distinct(self):
        now=datetime.now(timezone.utc); subject=Subject("o/r","a"*40)
        trials=tuple(CalibrationTrial("s",str(i),True,actual,now) for i,actual in enumerate([True,True,True,False])); est=estimate("s",trials)
        witnesses=(CurrentWitness("e",subject,"c","s","PASS",now),)
        scores={s:evaluate(s,witnesses,{"s":est}).score for s in FusionStrategy}
        self.assertEqual(scores[FusionStrategy.UNIFORM_CLUSTER],1); self.assertNotEqual(scores[FusionStrategy.UNIFORM_CLUSTER],scores[FusionStrategy.CALIBRATED_LOG_ODDS])
