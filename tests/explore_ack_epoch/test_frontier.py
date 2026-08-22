import unittest
from datetime import datetime,timezone
from gymact.explore_ack_epoch.epoch import Epoch
from gymact.explore_ack_epoch.frontier import current_epoch
class T(unittest.TestCase):
 def test_diverge(self):
  t=datetime.now(timezone.utc)
  with self.assertRaisesRegex(ValueError,"DIVERGENT"): current_epoch([Epoch(2,"a","a"*64,t),Epoch(2,"b","b"*64,t)])
