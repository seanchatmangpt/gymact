import unittest
from fractions import Fraction

from gymact.explore_replicated_projection_quorum.pareto import StrategyVector, pareto_frontier
from gymact.explore_replicated_projection_quorum.selectors import SelectorKind

class ParetoCourt(unittest.TestCase):
    def test_strictly_dominated_strategy_is_removed(self):
        good = StrategyVector(SelectorKind.STRICT_MAJORITY_CURRENTNESS, Fraction(4,5), Fraction(0), 0)
        bad = StrategyVector(SelectorKind.MAX_COVERAGE_FRESHNESS, Fraction(3,5), Fraction(1,5), 1)
        self.assertEqual(pareto_frontier((good, bad)), (good,))

if __name__ == "__main__":
    unittest.main()
