import unittest

from gymact.explore_rail_consensus.failure import CorrelatedFailureWorld
from gymact.explore_rail_consensus.storage import PersistenceNeed, Store, candidates, select


class FailureStorageTest(unittest.TestCase):
    def test_seed_replay_and_storage_frontier(self):
        world = CorrelatedFailureWorld(9, 0.5)
        self.assertEqual(
            world.failed_families(("a", "b", "c")), world.failed_families(("a", "b", "c"))
        )
        self.assertEqual(select(PersistenceNeed(transactional=True)), Store.SQLITE)
        self.assertEqual(set(candidates()), {Store.MEMORY, Store.JSONL, Store.SQLITE})
