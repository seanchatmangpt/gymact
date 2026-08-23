import unittest
from fractions import Fraction

from gymact.explore_realized_acquisition_feedback.calibration import GainCalibration
from gymact.explore_realized_acquisition_feedback.realization import (
    AcquisitionRealization,
)


class TestCalibration(unittest.TestCase):
    def test_support_gate(self):
        xs = [
            AcquisitionRealization(
                str(index), Fraction(1, 2), Fraction(1, 2), Fraction(1, 10), 1
            )
            for index in range(3)
        ]
        self.assertTrue(GainCalibration.fit(xs).calibrated)
