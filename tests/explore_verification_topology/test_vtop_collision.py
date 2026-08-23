import unittest
from gymact.explore_verification_topology.module_identity import TestModule
from gymact.explore_verification_topology.inventory import ModuleInventory
from gymact.explore_verification_topology.collision import collision_classes

class TestCollision(unittest.TestCase):
    def test_class(self):
        inventory = ModuleInventory.admit([
            TestModule("tests/a/test_x.py"),
            TestModule("tests/b/test_x.py"),
        ])
        self.assertEqual(collision_classes(inventory)[0].cardinality, 2)
