import unittest
from datetime import UTC, datetime, timedelta

from gymact.explore_intent_frontier.context import SelectionContext
from gymact.explore_intent_frontier.intent import SelectionIntent
from gymact.explore_intent_frontier.subject import Subject


class TestIntent(unittest.TestCase):
    def test_half_open_lease(self):
        c = SelectionContext(
            Subject("a/b", "1" * 40), "cut", "2" * 64, 1, "LATEST_COMPLETE", "3" * 64
        )
        t = datetime(2026, 8, 22, tzinfo=UTC)
        i = SelectionIntent(c, "nonce-0001", t, t + timedelta(minutes=5))
        self.assertTrue(i.active(t))
        self.assertFalse(i.active(t + timedelta(minutes=5)))
        with self.assertRaisesRegex(ValueError, "REFUSED_NAIVE_INTENT_LEASE"):
            SelectionIntent(c, "nonce-0002", datetime(2026, 8, 22), datetime(2026, 8, 23))


if __name__ == "__main__":
    unittest.main()
