import unittest
from datetime import datetime, timezone
from gymact.explore_invalidation.event import InvalidationEvent
from gymact.explore_invalidation.model import Subject
from gymact.explore_invalidation.standing import affected_standing

class T(unittest.TestCase):
    def test_failure_and_recovery(self):
        s=Subject("o/a","a"*40); now=datetime.now(timezone.utc)
        self.assertEqual(affected_standing("ALIVE",InvalidationEvent(s,"BUILD_BROKEN",now)),"BLOCKED")
        self.assertEqual(affected_standing("BLOCKED",InvalidationEvent(s,"RECOVERED",now)),"REQUALIFYING")
