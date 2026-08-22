import unittest
from datetime import datetime,timezone
from gymact.explore_ack_epoch.witness import Witness
from gymact.explore_ack_epoch.census import census
class T(unittest.TestCase):
 def test_states(self):
  t=datetime.now(timezone.utc); ws=(Witness("c",1,"e","DELIVERY","d",t),)
  self.assertEqual(census(["c","x"],ws),{"c":"DELIVERED","x":"PENDING"})
