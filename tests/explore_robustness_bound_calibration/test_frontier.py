import unittest
from fractions import Fraction

from gymact.explore_robustness_bound_calibration import Calibration, CalibrationSnapshot, Refused, current


class FrontierCourt(unittest.TestCase):
    def test_latest_generation_and_divergence(self) -> None:
        cal = Calibration(3, Fraction(1), Fraction(0), Fraction(1, 4))
        old = CalibrationSnapshot(1, "a" * 64, "m" * 64, cal)
        new = CalibrationSnapshot(2, "b" * 64, "m" * 64, cal)
        self.assertEqual(current((old, new)), new)
        with self.assertRaises(Refused):
            current((new, CalibrationSnapshot(2, "c" * 64, "n" * 64, cal)))


if __name__ == "__main__":
    unittest.main()
