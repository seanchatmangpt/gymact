import unittest
from fractions import Fraction

from gymact.explore_realized_acquisition_feedback.realization import (
    AcquisitionRealization,
)
from gymact.explore_realized_acquisition_feedback.regret import realized_regret


class TestRegret(unittest.TestCase):
    def test_regret(self):
        chosen = AcquisitionRealization(
            "a", Fraction(1, 2), Fraction(1, 4), Fraction(1, 10), 1
        )
        alternative = AcquisitionRealization(
            "b", Fraction(1, 2), Fraction(3, 4), Fraction(1, 10), 1
        )
        self.assertEqual(realized_regret(chosen, [alternative]), Fraction(1, 2))
