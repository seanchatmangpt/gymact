import unittest
from datetime import datetime, timezone
from gymact.explore_invalidation.engine import qualify, require_do
from gymact.explore_invalidation.event import InvalidationEvent
from gymact.explore_invalidation.graph import DependencyGraph
from gymact.explore_invalidation.model import Binding, Refusal, Subject

class T(unittest.TestCase):
    def test_failure_cascades_without_do(self):
        a=Subject("o/a","a"*40); b=Subject("o/b","b"*40); c=Subject("o/c","c"*40)
        g=DependencyGraph([Binding(a,b,"d"*64,"v1","REPOSITORY","1"),Binding(b,c,"e"*64,"v1","REPOSITORY","2")])
        q=qualify(g,InvalidationEvent(a,"BUILD_BROKEN",datetime.now(timezone.utc)))
        self.assertEqual(q.standing,"BLOCKED")
        self.assertEqual(len(q.cascade),2)
        self.assertFalse(q.receipt.payload["actuation_performed"])
        with self.assertRaisesRegex(Refusal,"UNRECEIPTED_ACTUATION"):
            require_do()
