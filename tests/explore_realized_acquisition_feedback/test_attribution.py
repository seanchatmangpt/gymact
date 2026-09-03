import unittest
from fractions import Fraction

from gymact.explore_realized_acquisition_feedback.attribution import (
    leave_one_out_contribution,
)
from gymact.explore_realized_acquisition_feedback.realization import (
    AcquisitionRealization,
)


class TestAttribution(unittest.TestCase):
    def test_sensor_contribution(self):
        xs = [
            AcquisitionRealization("a", Fraction(1, 2), Fraction(1, 3), Fraction(0), 1),
            AcquisitionRealization("b", Fraction(1, 2), Fraction(1, 4), Fraction(0), 1),
        ]
        self.assertEqual(leave_one_out_contribution(xs, "a"), Fraction(1, 3))
