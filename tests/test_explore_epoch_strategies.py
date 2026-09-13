import unittest

from gymact.explore_epoch.strategies import RolloverStrategy, evaluate
from gymact.explore_epoch.witness import WitnessKind


class TestEpochStrategies(unittest.TestCase):
    def test_strategies_remain_distinct(self):
        consumers = ("a", "b", "c")
        frontier = {"a": WitnessKind.DISCHARGED, "b": WitnessKind.DISCHARGED}
        self.assertFalse(evaluate(RolloverStrategy.EAGER_ALL, frontier, consumers).complete)
        self.assertTrue(evaluate(RolloverStrategy.QUORUM_MIGRATE, frontier, consumers).complete)


if __name__ == "__main__":
    unittest.main()
