import unittest
from gymact.explore_verification_topology.subject import Subject
from gymact.explore_verification_topology.module_identity import TestModule
from gymact.explore_verification_topology.inventory import ModuleInventory
from gymact.explore_verification_topology.engine import qualify
from gymact.explore_verification_topology.policies import CollectorPolicy
from gymact.explore_verification_topology.receipt import replay

class TestVerificationTopologyE2E(unittest.TestCase):
    def test_collision_frontier_is_reversible(self):
        inventory = ModuleInventory.admit([
            TestModule("tests/a/test_x.py"),
            TestModule("tests/b/test_x.py"),
        ])
        subject = Subject("seanchatmangpt/gymact", "d" * 40)
        strict = qualify(subject, inventory, CollectorPolicy.UNIQUE_BASENAME)
        importlib = qualify(subject, inventory, CollectorPolicy.IMPORTLIB)
        self.assertFalse(strict.admitted)
        self.assertTrue(importlib.admitted)
        self.assertTrue(replay(importlib.receipt, importlib.receipt.digest()))
        self.assertFalse(importlib.receipt.actuation_performed)
