import unittest
from fractions import Fraction

from gymact.explore_verification_acquisition.calibration import RailCalibration
from gymact.explore_verification_acquisition.capability import RailCapability
from gymact.explore_verification_acquisition.information import (
    binary_entropy,
    estimate_information,
)
from gymact.explore_verification_acquisition.subject import Subject


class InformationTest(unittest.TestCase):
    def test_informative_detector_reduces_expected_entropy(self):
        subject = Subject("o/r", "d" * 40)
        rail = RailCapability(subject, "a", "x", "y", frozenset({"unit"}), 10, 10)
        calibration = RailCalibration(rail, 10, Fraction(9, 10), Fraction(1, 10))
        estimate = estimate_information(Fraction(1, 2), calibration)
        self.assertGreater(estimate.information_gain, 0)
        self.assertLess(estimate.expected_entropy, binary_entropy(Fraction(1, 2)))
