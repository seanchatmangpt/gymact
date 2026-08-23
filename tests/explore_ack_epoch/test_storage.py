import unittest
from gymact.explore_ack_epoch.storage import stores,select_store
class T(unittest.TestCase):
 def test_candidates(self):
  self.assertEqual([x.name for x in stores()],["MEMORY","JSONL","SQLITE"]); self.assertEqual(select_store(transactional=True).name,"SQLITE")
