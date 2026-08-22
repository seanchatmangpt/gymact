import unittest

from gymact.explore_recovery_proof.admission import admit
from gymact.explore_recovery_proof.attempt import RecoveryAttempt
from gymact.explore_recovery_proof.context import RecoveryContext
from gymact.explore_recovery_proof.strategies import RecoveryProtocol
from gymact.explore_recovery_proof.subject import Refusal, Subject

SUBJECT = Subject("o/r@" + "1" * 40)
POLICY = "a" * 64


class TestAdmission(unittest.TestCase):
    def test_concurrent_target_movement_refuses_cas(self):
        base = RecoveryContext(SUBJECT, "a", "S", POLICY, 1)
        target = RecoveryContext(SUBJECT, "b", "S", POLICY, 2)
        current = RecoveryContext(SUBJECT, "c", "S", POLICY, 3)
        attempt = RecoveryAttempt.issue("x", 1, base, target, "CAS")
        with self.assertRaisesRegex(Refusal, "STALE_TARGET"):
            admit(attempt, base, target, current, RecoveryProtocol.CAS_RESELECT)

    def test_non_monotone_target_refuses(self):
        base = RecoveryContext(SUBJECT, "a", "S", POLICY, 2)
        target = RecoveryContext(SUBJECT, "b", "S", POLICY, 1)
        attempt = RecoveryAttempt.issue("x", 1, base, target, "CAS")
        with self.assertRaisesRegex(Refusal, "NON_MONOTONE"):
            admit(attempt, base, target, target, RecoveryProtocol.CAS_RESELECT)
