import unittest
from fractions import Fraction
from gymact.explore_realized_acquisition_feedback.frontier import PolicyVector, pareto_frontier

class TestFrontier(unittest.TestCase):
    def test_dominated_removed(self):
        a = PolicyVector("a", Fraction(1,10), Fraction(1,10), Fraction(1,10))
        b = PolicyVector("b", Fraction(1,2), Fraction(1,2), Fraction(1,2))
        self.assertEqual(pareto_frontier([a,b]), [a])
