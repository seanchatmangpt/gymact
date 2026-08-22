import unittest
from gymact.explore_verification_topology.storage import StoreKind, select_store
from gymact.explore_verification_topology.frontier import PlanWitness, current_frontier
from gymact.explore_verification_topology.policies import CollectorPolicy
from gymact.explore_verification_topology.subject import Refusal

class TestStorageFrontier(unittest.TestCase):
    def test_transactional_selects_sqlite(self):
        self.assertEqual(select_store(require_transactional=True).kind, StoreKind.SQLITE)

    def test_divergent_max_refused(self):
        witnesses = (
            PlanWitness(2, CollectorPolicy.IMPORTLIB, "a"),
            PlanWitness(2, CollectorPolicy.UNIQUE_BASENAME, "b"),
        )
        with self.assertRaisesRegex(Refusal, "DIVERGENT_PLAN_FRONTIER"):
            current_frontier(witnesses)
