import unittest
from gymact.explore_intent_frontier.storage import StoreKind,discover,select
class TestStorage(unittest.TestCase):
    def test_reversible_candidates_and_transactional_selection(self):
        self.assertEqual({c.kind for c in discover()},{StoreKind.MEMORY,StoreKind.JSONL,StoreKind.SQLITE})
        self.assertIs(select(durable=False,transactional=False).kind,StoreKind.MEMORY)
        self.assertIs(select(durable=True,transactional=False).kind,StoreKind.JSONL)
        self.assertIs(select(durable=True,transactional=True).kind,StoreKind.SQLITE)
if __name__=="__main__": unittest.main()
