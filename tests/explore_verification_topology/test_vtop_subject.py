import unittest
from gymact.explore_verification_topology.subject import Subject, Refusal

class TestSubject(unittest.TestCase):
    def test_exact(self):
        self.assertEqual(Subject("o/r", "a" * 40).sha, "a" * 40)

    def test_short_refused(self):
        with self.assertRaisesRegex(Refusal, "REFUSED_INEXACT_SUBJECT"):
            Subject("o/r", "abc")
