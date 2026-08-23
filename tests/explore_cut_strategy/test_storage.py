import unittest
from gymact.explore_cut_strategy.storage import CANDIDATES,StoreKind,select_store
class T(unittest.TestCase):
    def test_alternatives_preserved(self):
        self.assertEqual(len(CANDIDATES),3)
        self.assertEqual(select_store(transactional=True).kind,StoreKind.SQLITE)
        self.assertEqual(select_store(durable=True).kind,StoreKind.JSONL)
