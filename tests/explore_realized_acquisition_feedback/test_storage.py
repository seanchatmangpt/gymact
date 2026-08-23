import unittest
from gymact.explore_realized_acquisition_feedback.storage import StorageNeed, StoreKind, select_store

class TestStorage(unittest.TestCase):
    def test_transactionality_selects_sqlite(self):
        self.assertEqual(select_store(StorageNeed(durable=True, transactional=True)), StoreKind.SQLITE)
        self.assertEqual(select_store(StorageNeed(durable=True)), StoreKind.JSONL)
        self.assertEqual(select_store(StorageNeed()), StoreKind.MEMORY)
