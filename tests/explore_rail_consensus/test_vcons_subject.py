import unittest

from gymact.explore_rail_consensus.subject import Refusal, Subject

class SubjectTest(unittest.TestCase):
    def test_exact_identity_and_short_sha_refusal(self):
        subject = Subject("o/r", "a" * 40)
        self.assertEqual(subject.identity, "o/r@" + "a" * 40)
        with self.assertRaisesRegex(Refusal, "REFUSED_INEXACT_SUBJECT"):
            Subject("o/r", "a" * 8)
