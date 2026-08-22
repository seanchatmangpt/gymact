import unittest
from gymact.explore_verification_topology.module_identity import TestModule
from gymact.explore_verification_topology.inventory import ModuleInventory
from gymact.explore_verification_topology.comparison import pareto, vector
from gymact.explore_verification_topology.policies import CollectorPolicy

class TestPareto(unittest.TestCase):
    def test_frontier_preserves_tradeoffs(self):
        inventory = ModuleInventory.admit([
            TestModule("tests/a/test_x.py"),
            TestModule("tests/b/test_x.py"),
        ])
        vectors = tuple(vector(inventory, policy, {"tests/a", "tests/b"}) for policy in CollectorPolicy)
        frontier = pareto(vectors)
        self.assertGreaterEqual(len(frontier), 1)
        self.assertLessEqual(len(frontier), len(vectors))
