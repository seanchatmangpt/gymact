import unittest
from fractions import Fraction

from gymact.explore_robustness_bound_calibration import CandidateVector, frontier


class ParetoCourt(unittest.TestCase):
    def test_dominated_candidate_removed(self) -> None:
        strong = CandidateVector("strong", Fraction(9, 10), Fraction(3, 4), Fraction(1, 4))
        weak = CandidateVector("weak", Fraction(4, 5), Fraction(1, 2), Fraction(1, 2))
        tradeoff = CandidateVector("tradeoff", Fraction(19, 20), Fraction(2, 3), Fraction(1, 3))
        names = {candidate.name for candidate in frontier((strong, weak, tradeoff))}
        self.assertNotIn("weak", names)
        self.assertEqual(names, {"strong", "tradeoff"})


if __name__ == "__main__":
    unittest.main()
