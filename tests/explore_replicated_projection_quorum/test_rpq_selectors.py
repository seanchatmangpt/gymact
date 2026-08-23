import unittest

from gymact.explore_replicated_projection_quorum.refusal import Refused
from gymact.explore_replicated_projection_quorum.selectors import SelectorKind, select

from .world import UNIVERSE, projection


class SelectorCourt(unittest.TestCase):
    def test_strategies_preserve_distinct_currentness_rules(self):
        observations = (
            projection("r1", generation=1),
            projection("r2", generation=1),
            projection("r3", generation=1),
            projection("r4", generation=2, digest="c" * 64),
        )
        with self.assertRaises(Refused):
            select(SelectorKind.STRICT_MAJORITY_CURRENTNESS, observations, UNIVERSE)
        coverage = select(SelectorKind.MAX_COVERAGE_FRESHNESS, observations, UNIVERSE)
        self.assertEqual(coverage.generation, 1)
        with self.assertRaises(Refused):
            select(SelectorKind.CAUSAL_MAXIMA_CONSERVATIVE, observations, UNIVERSE)


if __name__ == "__main__":
    unittest.main()
