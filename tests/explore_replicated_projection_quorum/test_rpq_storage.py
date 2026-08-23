import unittest

from gymact.explore_replicated_projection_quorum.storage import CAPABILITIES, StorageKind, choose_storage

class StorageCourt(unittest.TestCase):
    def test_transactionality_selects_sqlite_without_erasing_alternatives(self):
        self.assertEqual({item.kind for item in CAPABILITIES}, {StorageKind.MEMORY, StorageKind.JSONL, StorageKind.SQLITE})
        self.assertIs(choose_storage(durable=True, transactional=True).kind, StorageKind.SQLITE)

if __name__ == "__main__":
    unittest.main()
