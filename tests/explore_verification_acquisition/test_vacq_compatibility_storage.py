import unittest

from gymact.explore_verification_acquisition.capability import RailCapability
from gymact.explore_verification_acquisition.compatibility import (
    PlanCompatibility,
    admit_compatible,
)
from gymact.explore_verification_acquisition.storage import (
    PersistenceNeed,
    Store,
    candidates,
    select,
)
from gymact.explore_verification_acquisition.subject import Refusal, Subject


class CompatibilityStorageTest(unittest.TestCase):
    def test_exact_plan_binding_and_storage_frontier(self):
        subject = Subject("o/r", "2" * 40)
        rail = RailCapability(subject, "a", "f", "d", frozenset({"unit"}), 5, 5)
        witness = PlanCompatibility(subject, (rail.fingerprint,))
        admit_compatible(subject, (rail,), witness)
        with self.assertRaisesRegex(Refusal, "REFUSED_STALE"):
            admit_compatible(subject, (), witness)
        self.assertEqual(select(PersistenceNeed(transactional=True)), Store.SQLITE)
        self.assertEqual(set(candidates()), {Store.MEMORY, Store.JSONL, Store.SQLITE})
