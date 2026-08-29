import unittest
from fractions import Fraction

from gymact.explore_robustness_bound_calibration import Refused, RobustnessBound


class BoundCourt(unittest.TestCase):
    def test_domain_and_width(self) -> None:
        bound = RobustnessBound(Fraction(1, 4), Fraction(3, 4), Fraction(2), "IPS", "b" * 64)
        self.assertEqual(bound.width, Fraction(1, 2))
        with self.assertRaises(Refused):
            RobustnessBound(Fraction(0), Fraction(1), Fraction(1, 2), "IPS", "b" * 64)


if __name__ == "__main__":
    unittest.main()
