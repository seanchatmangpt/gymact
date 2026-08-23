import unittest
from fractions import Fraction
from gymact.explore_methodology_correspondence.optimization import Candidate, frontier
from gymact.explore_methodology_correspondence.intervention import InterventionIntent, require_non_actuating

class TestOptimizationAuthority(unittest.TestCase):
    def test_frontier_and_do_refusal(self):
        a=Candidate('a',Fraction(2),Fraction(1)); b=Candidate('b',Fraction(1),Fraction(2))
        self.assertEqual(frontier((a,b)),(a,))
        with self.assertRaisesRegex(ValueError,'REFUSED_UNRECEIPTED_ACTUATION'):
            require_non_actuating(InterventionIntent('x','mutate','DO'))
