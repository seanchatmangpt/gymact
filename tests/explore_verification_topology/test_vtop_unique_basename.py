import unittest
from gymact.explore_verification_topology.module_identity import TestModule
from gymact.explore_verification_topology.inventory import ModuleInventory
from gymact.explore_verification_topology.admission import admit_policy
from gymact.explore_verification_topology.policies import CollectorPolicy

class TestUniqueBasename(unittest.TestCase):
    def test_collision_refused(self):
        inventory = ModuleInventory.admit([
            TestModule("tests/a/test_x.py"),
            TestModule("tests/b/test_x.py"),
        ])
        self.assertFalse(admit_policy(inventory, CollectorPolicy.UNIQUE_BASENAME).admitted)
