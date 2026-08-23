import unittest
from fractions import Fraction

from gymact.explore_causal_sensitivity import Gamma, LoggedOutcome, manski_mean, robust_ips, robust_snips


class IntervalEstimatorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.rows = (
            LoggedOutcome("c1", "a", Fraction(1), Fraction(1, 2), Fraction(1, 2)),
            LoggedOutcome("c2", "a", Fraction(0), Fraction(1, 2), Fraction(1, 2)),
        )

    def test_manski_interval_is_nontrivial_with_missingness(self) -> None:
        interval = manski_mean(Fraction(1), 2, 2, Fraction(0), Fraction(1))
        self.assertEqual(interval.lower, Fraction(1, 4))
        self.assertEqual(interval.upper, Fraction(3, 4))

    def test_gamma_one_collapses_robust_ips(self) -> None:
        interval = robust_ips(self.rows, Gamma(Fraction(1)))
        self.assertEqual(interval.lower, interval.upper)
        self.assertEqual(interval.lower, Fraction(1, 2))

    def test_snips_remains_distinct_contract(self) -> None:
        interval = robust_snips(self.rows, Gamma(Fraction(2)))
        self.assertLessEqual(interval.lower, interval.upper)


if __name__ == "__main__":
    unittest.main()
