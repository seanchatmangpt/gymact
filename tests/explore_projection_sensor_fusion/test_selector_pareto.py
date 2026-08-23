from fractions import Fraction
import unittest

from gymact.explore_projection_sensor_fusion.acquisition import AcquisitionCandidate
from gymact.explore_projection_sensor_fusion.budget import Budget
from gymact.explore_projection_sensor_fusion.pareto import frontier
from gymact.explore_projection_sensor_fusion.selectors import Selector, select


class SelectorParetoCourt(unittest.TestCase):
    def test_distinct_strategies_survive(self) -> None:
        fast = AcquisitionCandidate("fast", Fraction(2, 5), Fraction(1, 5), Fraction(1, 10), 10)
        rich = AcquisitionCandidate("rich", Fraction(4, 5), Fraction(4, 5), Fraction(1, 2), 40)
        dominated = AcquisitionCandidate("dominated", Fraction(1, 5), Fraction(1, 10), Fraction(3, 5), 50)
        candidates = (fast, rich, dominated)
        names = {candidate.sensor_id for candidate in frontier(candidates)}
        self.assertEqual(names, {"fast", "rich"})
        self.assertEqual(select((fast, rich), Selector.MIN_COST), fast)
        self.assertEqual(select((fast, rich), Selector.MAX_DISCRIMINATION), rich)
        self.assertTrue(Budget(Fraction(1, 5), 20).admits(fast))
        self.assertFalse(Budget(Fraction(1, 5), 20).admits(rich))


if __name__ == "__main__":
    unittest.main()
