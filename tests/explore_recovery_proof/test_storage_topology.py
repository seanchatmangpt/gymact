import unittest

from gymact.explore_recovery_proof.storage import StoreKind, discover, select
from gymact.explore_recovery_proof.subject import Refusal
from gymact.explore_recovery_proof.topology import DependencyGraph


class TestStorageTopology(unittest.TestCase):
    def test_storage_alternatives_and_transactional_selection(self):
        self.assertEqual(len(discover()), 3)
        self.assertEqual(select(transactional=True).kind, StoreKind.SQLITE)

    def test_cycle_refuses_and_blocker_propagates(self):
        with self.assertRaisesRegex(Refusal, "CYCLE"):
            DependencyGraph({"a": ("b",), "b": ("a",)})
        graph = DependencyGraph({"a": ("b",), "b": ()})
        self.assertEqual(graph.blockers({"b": "BUILD_BROKEN"})["a"], ("b",))
