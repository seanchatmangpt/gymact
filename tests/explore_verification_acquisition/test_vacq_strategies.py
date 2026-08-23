import unittest
from fractions import Fraction

from gymact.explore_verification_acquisition.calibration import RailCalibration
from gymact.explore_verification_acquisition.capability import RailCapability
from gymact.explore_verification_acquisition.strategies import AcquisitionStrategy, score
from gymact.explore_verification_acquisition.subject import Subject


class StrategyTest(unittest.TestCase):
    def test_distinct_policy_scores_and_seed_replay(self):
        subject = Subject("o/r", "e" * 40)
        rail = RailCapability(subject, "a", "x", "y", frozenset({"unit"}), 100, 10)
        calibration = RailCalibration(rail, 10, Fraction(9, 10), Fraction(1, 10))
        info = score(
            calibration,
            AcquisitionStrategy.MAX_INFORMATION,
            Fraction(1, 2),
            total_trials=10,
        )
        per_cost = score(
            calibration,
            AcquisitionStrategy.INFORMATION_PER_COST,
            Fraction(1, 2),
            total_trials=10,
        )
        self.assertNotEqual(info.value, per_cost.value)
        left = score(
            calibration,
            AcquisitionStrategy.THOMPSON_DISCOVERY,
            Fraction(1, 2),
            total_trials=10,
            seed=9,
        )
        right = score(
            calibration,
            AcquisitionStrategy.THOMPSON_DISCOVERY,
            Fraction(1, 2),
            total_trials=10,
            seed=9,
        )
        self.assertEqual(left, right)
