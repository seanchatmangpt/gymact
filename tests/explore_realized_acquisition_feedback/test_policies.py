import unittest
from fractions import Fraction
from gymact.explore_realized_acquisition_feedback.calibration import GainCalibration
from gymact.explore_realized_acquisition_feedback.policies import FeedbackPolicy, policy_score

class TestPolicies(unittest.TestCase):
    def test_distinct_scores(self):
        c = GainCalibration(4, Fraction(-1,4), Fraction(1,3))
        scores = {policy_score(p, c, True, Fraction(1,5)) for p in FeedbackPolicy}
        self.assertGreaterEqual(len(scores), 4)
