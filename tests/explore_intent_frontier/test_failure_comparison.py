import unittest

from gymact.explore_intent_frontier.comparison import pareto, score
from gymact.explore_intent_frontier.context import SelectionContext
from gymact.explore_intent_frontier.failure import inject
from gymact.explore_intent_frontier.strategies import FreshnessStrategy, decide
from gymact.explore_intent_frontier.subject import Subject


class TestFailureComparison(unittest.TestCase):
    def test_seeded_failure_and_pareto_are_deterministic(self):
        c = SelectionContext(Subject("a/b", "1" * 40), "cut", "2" * 64, 1, "MIN_SKEW", "3" * 64)
        a = inject(c, 7, "policy")
        b = inject(c, 7, "policy")
        self.assertEqual(a, b)
        rows = tuple(score(decide(s, c, a)) for s in FreshnessStrategy)
        self.assertEqual(pareto(rows), pareto(rows))
        self.assertGreaterEqual(len(pareto(rows)), 1)


if __name__ == "__main__":
    unittest.main()
