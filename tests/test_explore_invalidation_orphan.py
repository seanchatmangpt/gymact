import unittest
from datetime import datetime, timezone
from gymact.explore_invalidation.admission import admit_event
from gymact.explore_invalidation.event import InvalidationEvent
from gymact.explore_invalidation.graph import DependencyGraph
from gymact.explore_invalidation.model import Binding, Refusal, Subject

class T(unittest.TestCase):
    def test_orphan_refused(self):
        a=Subject("o/a","a"*40); b=Subject("o/b","b"*40); x=Subject("o/x","c"*40)
        g=DependencyGraph([Binding(a,b,"d"*64,"v1","FOCUSED","1")])
        with self.assertRaisesRegex(Refusal,"ORPHAN"):
            admit_event(g,InvalidationEvent(x,"NEW_HEAD",datetime.now(timezone.utc)))
