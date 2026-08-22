import unittest
from gymact.explore_ack_epoch.strategy import Strategy,complete,candidates
class T(unittest.TestCase):
 def test_distinct(self):
  s={"a":"DISCHARGED","b":"DISCHARGED","c":"PENDING"}
  self.assertFalse(complete(Strategy("ALL"),s)); self.assertTrue(complete(Strategy("QUORUM"),s)); self.assertEqual(len(candidates()),3)
