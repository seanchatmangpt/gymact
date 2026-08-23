import unittest
from datetime import datetime,timezone
from gymact.explore_ack_epoch.epoch import Epoch
from gymact.explore_ack_epoch.witness import Witness
from gymact.explore_ack_epoch.admission import admit
class T(unittest.TestCase):
 def test_gap(self):
  t=datetime.now(timezone.utc); e=Epoch(1,"e","d"*64,t); w=Witness("c",1,"e","ACK","a",t,parent_id="missing")
  with self.assertRaisesRegex(ValueError,"CAUSAL_GAP"): admit(e,[w])
