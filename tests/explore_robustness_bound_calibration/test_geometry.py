import unittest
from fractions import Fraction

from gymact.explore_robustness_bound_calibration import (
    RobustnessBound,
    identification_value,
    interval_iou,
)


class GeometryCourt(unittest.TestCase):
    def test_exact_interval_geometry(self) -> None:
        left = RobustnessBound(
            Fraction(0), Fraction(1, 2), Fraction(1), "IPS", "a" * 64
        )
        right = RobustnessBound(
            Fraction(1, 4), Fraction(3, 4), Fraction(1), "SNIPS", "b" * 64
        )
        self.assertEqual(interval_iou(left, right), Fraction(1, 3))
        self.assertEqual(identification_value(left, Fraction(1)), Fraction(1, 2))


if __name__ == "__main__":
    unittest.main()
