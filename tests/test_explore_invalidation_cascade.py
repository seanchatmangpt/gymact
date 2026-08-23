import unittest
from datetime import datetime, timezone
from gymact.explore_invalidation.cascade import cascade
from gymact.explore_invalidation.event import InvalidationEvent
from gymact.explore_invalidation.graph import DependencyGraph
from gymact.explore_invalidation.model import Binding, Subject

class T(unittest.TestCase):
    def test_transitive_depth(self):
        a=Subject("o/a","a"*40); b=Subject("o/b","b"*40); c=Subject("o/c","c"*40)
        g=DependencyGraph([Binding(a,b,"d"*64,"v1","FOCUSED","1"),Binding(b,c,"e"*64,"v1","FOCUSED","2")])
        self.assertEqual([x.depth for x in cascade(g,InvalidationEvent(a,"NEW_HEAD",datetime.now(timezone.utc)))],[1,2])
