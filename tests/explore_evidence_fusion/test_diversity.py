import unittest
from fractions import Fraction
from gymact.explore_evidence_fusion.diversity import inverse_simpson_effective_size
class T(unittest.TestCase):
 def test_exact_inverse_simpson(self):
  self.assertEqual(inverse_simpson_effective_size(((1,2),(3,),(4,))),Fraction(8,3))
