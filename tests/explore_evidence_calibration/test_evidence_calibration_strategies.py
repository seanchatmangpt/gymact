import unittest
from datetime import UTC, datetime

from gymact.explore_evidence_calibration.contracts import Subject
from gymact.explore_evidence_calibration.estimate import estimate
from gymact.explore_evidence_calibration.strategies import FusionStrategy, evaluate
from gymact.explore_evidence_calibration.trials import CalibrationTrial
from gymact.explore_evidence_calibration.witness import CurrentWitness


class StrategyTests(unittest.TestCase):
    def test_strategies_remain_distinct(self):
        now = datetime.now(UTC)
        subject = Subject("o/r", "a" * 40)
        outcomes = [True, True, True, False]
        trials = tuple(
            CalibrationTrial("s", str(index), True, actual, now)
            for index, actual in enumerate(outcomes)
        )
        estimate_value = estimate("s", trials)
        witnesses = (CurrentWitness("e", subject, "c", "s", "PASS", now),)
        scores = {
            strategy: evaluate(strategy, witnesses, {"s": estimate_value}).score
            for strategy in FusionStrategy
        }
        self.assertEqual(scores[FusionStrategy.UNIFORM_CLUSTER], 1)
        self.assertNotEqual(
            scores[FusionStrategy.UNIFORM_CLUSTER],
            scores[FusionStrategy.CALIBRATED_LOG_ODDS],
        )
