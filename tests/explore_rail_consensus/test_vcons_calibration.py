import unittest
from fractions import Fraction

from gymact.explore_rail_consensus.calibration import RailCalibration


class CalibrationTest(unittest.TestCase):
    def test_support_and_quality_states(self):
        self.assertEqual(
            RailCalibration(2, Fraction(0), Fraction(0), Fraction(1)).state(), "INSUFFICIENT"
        )
        self.assertEqual(
            RailCalibration(8, Fraction(1, 10), Fraction(1, 10), Fraction(1)).state(), "CALIBRATED"
        )
        self.assertEqual(
            RailCalibration(8, Fraction(1, 2), Fraction(0), Fraction(1)).state(), "UNRELIABLE"
        )
