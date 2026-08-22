import unittest
from gymact.explore_verification_topology.module_identity import TestModule
from gymact.explore_verification_topology.inventory import ModuleInventory
from gymact.explore_verification_topology.failure import FailureWorld, inject_collisions
from gymact.explore_verification_topology.collision import collision_classes

class TestFailureWorld(unittest.TestCase):
    def test_seeded_replay(self):
        inventory = ModuleInventory.admit([
            TestModule("tests/a/test_x.py"),
            TestModule("tests/b/test_y.py"),
        ])
        first = inject_collisions(inventory, FailureWorld(7, 2))
        second = inject_collisions(inventory, FailureWorld(7, 2))
        self.assertEqual(first.paths(), second.paths())
        self.assertTrue(collision_classes(first))
