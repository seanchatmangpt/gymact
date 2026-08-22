import unittest
from datetime import datetime, timezone

from gymact.explore_recovery_proof.attempt import RecoveryAttempt
from gymact.explore_recovery_proof.context import RecoveryContext
from gymact.explore_recovery_proof.drift import DriftKind, classify
from gymact.explore_recovery_proof.subject import Refusal, Subject

SUBJECT = Subject("o/r@" + "1" * 40)
POLICY = "a" * 64


class TestDriftAttempt(unittest.TestCase):
    def test_multi_axis_drift_and_attempt_identity(self):
        before = RecoveryContext(SUBJECT, "c1", "A", POLICY, 1)
        after = RecoveryContext(SUBJECT, "c2", "B", "b" * 64, 2)
        self.assertEqual(classify(before, after).kind, DriftKind.MULTI)
        attempt = RecoveryAttempt.issue("x", 1, before, after, "CAS", datetime.now(timezone.utc))
        self.assertEqual(len(attempt.identity), 64)

    def test_naive_time_refuses(self):
        context = RecoveryContext(SUBJECT, "c", "A", POLICY, 1)
        with self.assertRaisesRegex(Refusal, "NAIVE"):
            RecoveryAttempt(
                "x", 1, context.fingerprint, context.fingerprint, "CAS", datetime.now()
            )
