import unittest
from fractions import Fraction
from gymact.explore_verification_topology.module_identity import TestModule
from gymact.explore_verification_topology.inventory import ModuleInventory
from gymact.explore_verification_topology.metrics import measure

class TestMetrics(unittest.TestCase):
    def test_exact_density(self):
        inventory = ModuleInventory.admit([
            TestModule("tests/a/test_x.py"),
            TestModule("tests/b/test_x.py"),
            TestModule("tests/c/test_y.py"),
        ])
        self.assertEqual(measure(inventory).collision_density, Fraction(2, 3))
