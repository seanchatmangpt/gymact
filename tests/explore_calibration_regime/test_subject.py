import unittest
from gymact.explore_calibration_regime.subject import Subject
from gymact.explore_calibration_regime.refusal import Refusal
class T(unittest.TestCase):
 def test_exact(self):
  self.assertEqual(Subject("o/r","a"*40).sha,"a"*40)
  with self.assertRaises(Refusal): Subject("o/r","abc")
