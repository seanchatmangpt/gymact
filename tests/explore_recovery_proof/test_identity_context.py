import unittest

from gymact.explore_recovery_proof.context import RecoveryContext
from gymact.explore_recovery_proof.subject import Refusal, Subject

POLICY = "a" * 64


class TestIdentityContext(unittest.TestCase):
    def test_exact_subject_and_context_are_deterministic(self):
        subject = Subject("o/r@" + "1" * 40)
        left = RecoveryContext(subject, "cut", "LATEST", POLICY, 2)
        right = RecoveryContext(subject, "cut", "LATEST", POLICY, 2)
        self.assertEqual(left.fingerprint, right.fingerprint)

    def test_inexact_subject_refuses(self):
        with self.assertRaisesRegex(Refusal, "REFUSED_INEXACT_SUBJECT"):
            Subject("o/r@abc")
