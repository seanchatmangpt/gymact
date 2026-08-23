import unittest
from fractions import Fraction

from gymact.explore_robustness_bound_calibration import Refused, RobustnessBound, require_monotone


class MonotonicityCourt(unittest.TestCase):
    def test_gamma_envelope_cannot_narrow(self) -> None:
        wide = RobustnessBound(Fraction(0), Fraction(1), Fraction(2), "IPS", "b" * 64)
        base = RobustnessBound(Fraction(1, 4), Fraction(3, 4), Fraction(1), "IPS", "b" * 64)
        self.assertEqual(require_monotone((wide, base)), (base, wide))
        bad = RobustnessBound(Fraction(1, 3), Fraction(2, 3), Fraction(3), "IPS", "b" * 64)
        with self.assertRaises(Refused):
            require_monotone((base, wide, bad))


if __name__ == "__main__":
    unittest.main()
