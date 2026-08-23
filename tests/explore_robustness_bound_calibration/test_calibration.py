import unittest
from datetime import datetime, timezone
from fractions import Fraction

from gymact.explore_robustness_bound_calibration import BoundCase, Calibration, RobustnessBound, Subject


class CalibrationCourt(unittest.TestCase):
    def test_exact_coverage_and_width(self) -> None:
        subject = Subject("seanchatmangpt/gymact@" + "a" * 40)
        bound = RobustnessBound(Fraction(0), Fraction(1), Fraction(1), "IPS", "b" * 64)
        cases = tuple(BoundCase(subject, bound, truth, datetime(2026, 1, 1, tzinfo=timezone.utc), str(i)) for i, truth in enumerate((Fraction(0), Fraction(1, 2), Fraction(2))))
        calibration = Calibration.from_cases(cases)
        self.assertEqual(calibration.coverage, Fraction(2, 3))
        self.assertEqual(calibration.mean_width, Fraction(1))


if __name__ == "__main__":
    unittest.main()
