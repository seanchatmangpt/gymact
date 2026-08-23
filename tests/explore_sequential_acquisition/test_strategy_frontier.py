import unittest
from fractions import Fraction
from gymact.explore_sequential_acquisition.frontier import ObjectiveVector, pareto_frontier
from gymact.explore_sequential_acquisition.strategy import CandidateScore, Strategy, score


class StrategyCourt(unittest.TestCase):
    def test_distinct_scores_and_frontier(self):
        c = CandidateScore("s", Fraction(3, 4), Fraction(1, 2), Fraction(1, 4), Fraction(1, 3), Fraction(2, 3))
        self.assertNotEqual(score(c, Strategy.MAX_INFORMATION), score(c, Strategy.INFORMATION_PER_COST))
        strong = ObjectiveVector("a", Fraction(3, 4), Fraction(3, 4), Fraction(1), 10)
        weak = ObjectiveVector("b", Fraction(1, 2), Fraction(1, 2), Fraction(2), 20)
        self.assertEqual(pareto_frontier((strong, weak)), (strong,))


if __name__ == "__main__":
    unittest.main()
