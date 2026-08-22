import unittest
from gymact.explore_ack_epoch.subject import Subject
class T(unittest.TestCase):
 def test_exact(self):
  self.assertTrue(Subject("o/r","a"*40).identity.endswith("a"*40))
  with self.assertRaisesRegex(ValueError,"INEXACT"): Subject("o/r","abc")
