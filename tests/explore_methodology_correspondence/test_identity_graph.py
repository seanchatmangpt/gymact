import unittest
from fractions import Fraction
from gymact.explore_methodology_correspondence.identity import Subject, Refusal
from gymact.explore_methodology_correspondence.graph import shortest_path
from gymact.explore_methodology_correspondence.witness import Witness

class TestIdentityGraph(unittest.TestCase):
    def test_subject_and_path(self):
        with self.assertRaises(Refusal): Subject('o/r','abc')
        s=Subject('o/r','a'*40); self.assertTrue(s.identity.endswith('a'*40))
        e=Witness('EVENT','OBJECT',frozenset({'order'}),frozenset(),Fraction(1,1))
        self.assertEqual(shortest_path([e],'EVENT','OBJECT',frozenset({'order'})),(e,))
