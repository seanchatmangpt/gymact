import unittest
from datetime import UTC, datetime
from fractions import Fraction

from gymact.explore_evidence_calibration.estimate import estimate
from gymact.explore_evidence_calibration.trials import CalibrationTrial


class EstimateTests(unittest.TestCase):
    def test_smoothed_estimate_and_support(self):
        now = datetime.now(UTC)
        outcomes = [(True, True), (True, True), (True, False), (False, False)]
        trials = tuple(
            CalibrationTrial("s", str(index), predicted, actual, now)
            for index, (predicted, actual) in enumerate(outcomes)
        )
        result = estimate("s", trials)
        self.assertEqual(result.support, 4)
        self.assertEqual(result.true_positive_rate, Fraction(3, 4))
        self.assertEqual(result.false_positive_rate, Fraction(2, 4))
        self.assertTrue(result.calibrated)
