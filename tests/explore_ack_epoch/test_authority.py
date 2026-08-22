import unittest
from gymact.explore_ack_epoch.authority import require
class T(unittest.TestCase):
 def test_do_refused(self):
  with self.assertRaisesRegex(PermissionError,"REFUSED_UNRECEIPTED_ACTUATION"): require("DO")
