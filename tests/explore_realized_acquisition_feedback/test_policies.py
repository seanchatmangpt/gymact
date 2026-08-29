import unittest
from fractions import Fraction

from gymact.explore_realized_acquisition_feedback.calibration import GainCalibration
from gymact.explore_realized_acquisition_feedback.policies import (
    FeedbackPolicy,
    policy_score,
)


class TestPolicies(unittest.TestCase):
    def test_distinct_scores(self):
        calibration = GainCalibration(4, Fraction(-1, 4), Fraction(1, 3))
        scores = {
            policy_score(policy, calibration, True, Fraction(1, 5))
            for policy in FeedbackPolicy
        }
        self.assertGreaterEqual(len(scores), 4)
