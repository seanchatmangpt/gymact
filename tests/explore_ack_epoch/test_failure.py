import unittest
from gymact.explore_ack_epoch.failure import failure_plan
class T(unittest.TestCase):
 def test_replay(self):
  self.assertEqual(failure_plan(["b","a"],7,.4),failure_plan(["a","b"],7,.4))
