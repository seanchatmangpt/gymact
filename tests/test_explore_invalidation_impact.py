import unittest
from datetime import datetime, timezone
from gymact.explore_invalidation.event import InvalidationEvent
from gymact.explore_invalidation.impact import direct_impact
from gymact.explore_invalidation.model import Binding, Subject

class T(unittest.TestCase):
    def test_reason_preserved(self):
        a=Subject("o/a","a"*40); b=Subject("o/b","b"*40); x=Binding(a,b,"c"*64,"v1","FOCUSED","1")
        self.assertEqual(direct_impact(x,InvalidationEvent(a,"BUILD_BROKEN",datetime.now(timezone.utc))).reason,"PRODUCER_BUILD_BROKEN")
