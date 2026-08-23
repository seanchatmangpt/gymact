import unittest
from fractions import Fraction

from gymact.explore_robustness_bound_calibration import (
    Calibration,
    Refused,
    RobustnessBound,
    admit_bound,
)


class AdmissionCourt(unittest.TestCase):
    def test_width_and_coverage_gate(self) -> None:
        bound = RobustnessBound(Fraction(1, 4), Fraction(3, 4), Fraction(1), "IPS", "a" * 64)
        good = Calibration(5, Fraction(4, 5), Fraction(1, 5), Fraction(1, 2))
        admit_bound(
            bound,
            good,
            minimum_coverage=Fraction(3, 4),
            maximum_mean_width=Fraction(1, 2),
            maximum_bound_width=Fraction(1, 2),
        )
        bad = Calibration(5, Fraction(1, 2), Fraction(1, 2), Fraction(1, 2))
        with self.assertRaises(Refused):
            admit_bound(
                bound,
                bad,
                minimum_coverage=Fraction(3, 4),
                maximum_mean_width=Fraction(1, 2),
                maximum_bound_width=Fraction(1, 2),
            )


if __name__ == "__main__":
    unittest.main()
