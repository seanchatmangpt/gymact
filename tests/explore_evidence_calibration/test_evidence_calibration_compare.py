import unittest
from gymact.explore_evidence_calibration.compare import StrategyVector,pareto
class CompareTests(unittest.TestCase):
    def test_dominated_candidate_removed(self):
        weak=StrategyVector("weak",1,1,1); strong=StrategyVector("strong",2,2,2)
        self.assertEqual([v.strategy for v in pareto((weak,strong))],["strong"])
