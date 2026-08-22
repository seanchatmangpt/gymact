import unittest
from gymact.explore_cut_strategy.dependency import DependencyGraph
class T(unittest.TestCase):
    def test_cycle_refusal_and_closure(self):
        g=DependencyGraph({"root":("dep",),"dep":()})
        self.assertEqual(g.closure("root"),("dep","root"))
        with self.assertRaisesRegex(ValueError,"REFUSED_DEPENDENCY_CYCLE"):
            DependencyGraph({"a":("b",),"b":("a",)})
