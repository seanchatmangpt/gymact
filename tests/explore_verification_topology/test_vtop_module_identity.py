import unittest
from gymact.explore_verification_topology.module_identity import TestModule
from gymact.explore_verification_topology.inventory import ModuleInventory
from gymact.explore_verification_topology.subject import Refusal

class TestModuleIdentity(unittest.TestCase):
    def test_identity(self):
        self.assertEqual(TestModule("tests/a/test_x.py").basename, "test_x.py")

    def test_duplicate_path_refused(self):
        module = TestModule("tests/a/test_x.py")
        with self.assertRaisesRegex(Refusal, "DUPLICATE_TEST_PATH"):
            ModuleInventory.admit([module, module])
