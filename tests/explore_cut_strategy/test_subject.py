import unittest
from datetime import UTC, datetime

from gymact.explore_cut_strategy.subject import Subject

NOW = datetime(2026, 8, 22, 15, 0, tzinfo=UTC)


class T(unittest.TestCase):
    def test_exact_only(self):
        self.assertEqual(Subject.parse("a/r@" + "a" * 40).sha, "a" * 40)
        with self.assertRaisesRegex(ValueError, "REFUSED_INEXACT_SUBJECT"):
            Subject.parse("a/r@abc")
