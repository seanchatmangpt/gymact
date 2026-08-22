import unittest

from gymact.explore_verification_acquisition.capability import RailCapability
from gymact.explore_verification_acquisition.coverage import Coverage
from gymact.explore_verification_acquisition.pareto import StrategyVector, pareto_frontier
from gymact.explore_verification_acquisition.strategies import AcquisitionStrategy
from gymact.explore_verification_acquisition.subject import Subject


class CoverageParetoTest(unittest.TestCase):
    def test_coverage_and_strict_dominance(self):
        subject = Subject("o/r", "1" * 40)
        rail = RailCapability(
            subject,
            "a",
            "f",
            "d",
            frozenset({"unit", "integration"}),
            5,
            5,
        )
        ratio = Coverage(frozenset({"unit", "integration", "e2e"})).ratio((rail,))
        self.assertAlmostEqual(ratio, 2 / 3)
        weak = StrategyVector(AcquisitionStrategy.MAX_INFORMATION, 1.0, 0.5, 10, 10)
        strong = StrategyVector(AcquisitionStrategy.MINIMAX_COVERAGE, 1.0, 1.0, 9, 9)
        self.assertEqual(pareto_frontier((weak, strong)), (strong,))
