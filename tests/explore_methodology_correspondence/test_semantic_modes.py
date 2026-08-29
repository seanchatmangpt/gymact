import unittest
from gymact.explore_methodology_correspondence.declarative import Constraint, satisfies
from gymact.explore_methodology_correspondence.procedural import Transition, accepts
from gymact.explore_methodology_correspondence.powl import POWLNode, bounded_reachable

class TestSemanticModes(unittest.TestCase):
    def test_distinct_semantics(self):
        self.assertTrue(satisfies(('A','B'),(Constraint('A','B'),)))
        self.assertEqual(accepts('s',('A','B'),(Transition('s','A','m'),Transition('m','B','e'))),'e')
        nodes=(POWLNode('s',('s','e')),POWLNode('e',()))
        self.assertTrue(bounded_reachable(nodes,'s','e',2))
