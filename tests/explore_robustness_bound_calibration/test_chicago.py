import unittest
from fractions import Fraction

from gymact.explore_robustness_bound_calibration import (
    Calibration,
    CalibrationSnapshot,
    RobustnessBound,
    Subject,
    qualify,
    replay,
)


class ChicagoCourt(unittest.TestCase):
    def test_current_calibrated_bound_reaches_partial_alive_without_do(self) -> None:
        subject = Subject("seanchatmangpt/gymact@" + "a" * 40)
        bound = RobustnessBound(Fraction(1, 4), Fraction(3, 4), Fraction(2), "ROBUST_IPS", "b" * 64)
        calibration = Calibration(5, Fraction(4, 5), Fraction(1, 5), Fraction(1, 2))
        snapshot = CalibrationSnapshot(3, "c" * 64, "b" * 64, calibration)
        result = qualify(
            subject,
            bound,
            calibration,
            snapshot,
            (snapshot,),
            minimum_coverage=Fraction(3, 4),
            maximum_mean_width=Fraction(1, 2),
            maximum_bound_width=Fraction(1, 2),
            domain_width=Fraction(1),
        )
        self.assertEqual(result.standing, "PARTIAL_ALIVE")
        self.assertFalse(result.receipt.actuation_performed)
        self.assertTrue(replay(result.receipt, result.receipt.digest))


if __name__ == "__main__":
    unittest.main()
