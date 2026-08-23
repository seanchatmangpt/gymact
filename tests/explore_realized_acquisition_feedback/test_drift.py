import unittest
from fractions import Fraction
from gymact.explore_realized_acquisition_feedback.drift import CusumDrift

class TestDrift(unittest.TestCase):
    def test_alarm(self):
        d = CusumDrift(Fraction(1,2))
        self.assertFalse(d.update(Fraction(1,4)))
        self.assertTrue(d.update(Fraction(1,4)))
