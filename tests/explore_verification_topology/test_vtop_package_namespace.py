import unittest
from gymact.explore_verification_topology.module_identity import TestModule
from gymact.explore_verification_topology.inventory import ModuleInventory
from gymact.explore_verification_topology.admission import admit_policy
from gymact.explore_verification_topology.policies import CollectorPolicy

class TestPackageNamespace(unittest.TestCase):
    def test_markers_required(self):
        inventory = ModuleInventory.admit([
            TestModule("tests/a/test_x.py"),
            TestModule("tests/b/test_x.py"),
        ])
        self.assertFalse(admit_policy(inventory, CollectorPolicy.PACKAGE_NAMESPACE, {"tests/a"}).admitted)
        self.assertTrue(admit_policy(inventory, CollectorPolicy.PACKAGE_NAMESPACE, {"tests/a", "tests/b"}).admitted)
