import unittest
from datetime import datetime, timezone
from gymact.explore_invalidation.event import InvalidationEvent
from gymact.explore_invalidation.model import Refusal, Subject

class T(unittest.TestCase):
    def test_event_requires_tz_and_replacement(self):
        s=Subject("o/r","a"*40)
        with self.assertRaisesRegex(Refusal,"INVALID_INVALIDATION_EVENT"):
            InvalidationEvent(s,"NEW_HEAD",datetime.now())
        with self.assertRaisesRegex(Refusal,"MISSING_REPLACEMENT"):
            InvalidationEvent(s,"NEW_RECEIPT",datetime.now(timezone.utc))
