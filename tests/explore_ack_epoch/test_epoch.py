import unittest
from datetime import datetime,timezone
from gymact.explore_ack_epoch.epoch import Epoch
class T(unittest.TestCase):
 def test_epoch(self):
  Epoch(2,"e","b"*64,datetime.now(timezone.utc))
  with self.assertRaisesRegex(ValueError,"INVALID_EPOCH"): Epoch(-1,"e","b"*64,datetime.now(timezone.utc))
