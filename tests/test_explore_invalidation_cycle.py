import unittest
from gymact.explore_invalidation.graph import DependencyGraph
from gymact.explore_invalidation.model import Binding, Refusal, Subject

class T(unittest.TestCase):
    def test_cycle_refused(self):
        a=Subject("o/a","a"*40); b=Subject("o/b","b"*40)
        with self.assertRaisesRegex(Refusal,"DEPENDENCY_CYCLE"):
            DependencyGraph([Binding(a,b,"c"*64,"v1","FOCUSED","1"),Binding(b,a,"d"*64,"v1","FOCUSED","2")])
