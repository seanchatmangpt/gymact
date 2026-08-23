import unittest

from gymact.explore_realized_acquisition_feedback.storage import (
    StorageNeed,
    StoreKind,
    select_store,
)


class TestStorage(unittest.TestCase):
    def test_transactionality_selects_sqlite(self):
        transactional = StorageNeed(durable=True, transactional=True)
        self.assertEqual(select_store(transactional), StoreKind.SQLITE)
        self.assertEqual(select_store(StorageNeed(durable=True)), StoreKind.JSONL)
        self.assertEqual(select_store(StorageNeed()), StoreKind.MEMORY)
