import unittest
from datetime import datetime,timezone
from gymact.explore_ack_epoch.epoch import Epoch
from gymact.explore_ack_epoch.witness import Witness
from gymact.explore_ack_epoch.admission import admit
class T(unittest.TestCase):
 def test_stale(self):
  e=Epoch(3,"e","c"*64,datetime.now(timezone.utc)); w=Witness("c",2,"e","DELIVERY","w",datetime.now(timezone.utc))
  with self.assertRaisesRegex(ValueError,"STALE_INVALIDATION_EPOCH"): admit(e,[w])
