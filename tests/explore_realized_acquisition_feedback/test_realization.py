import unittest
from fractions import Fraction

from gymact.explore_realized_acquisition_feedback.realization import (
    AcquisitionRealization,
)


class TestRealization(unittest.TestCase):
    def test_gain_error(self):
        realization = AcquisitionRealization(
            "s", Fraction(3, 4), Fraction(1, 2), Fraction(1, 10), 5
        )
        self.assertEqual(realization.gain_error, Fraction(-1, 4))
