import unittest
from datetime import datetime, timezone
from gymact.explore_invalidation.engine import qualify
from gymact.explore_invalidation.event import InvalidationEvent
from gymact.explore_invalidation.graph import DependencyGraph
from gymact.explore_invalidation.model import Binding, Refusal, Subject
from gymact.explore_invalidation.replay import tamper, verify_receipt

class T(unittest.TestCase):
    def test_replay_tamper_refused(self):
        a=Subject("o/a","a"*40); b=Subject("o/b","b"*40); g=DependencyGraph([Binding(a,b,"c"*64,"v1","FOCUSED","1")])
        q=qualify(g,InvalidationEvent(a,"NEW_HEAD",datetime.now(timezone.utc)))
        self.assertTrue(verify_receipt(q.receipt))
        with self.assertRaisesRegex(Refusal,"REPLAY_MISMATCH"):
            verify_receipt(tamper(q.receipt,standing="ALIVE"))
