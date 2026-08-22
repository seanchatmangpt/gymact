import unittest

from gymact.explore_recovery_proof.admission import admit
from gymact.explore_recovery_proof.attempt import RecoveryAttempt
from gymact.explore_recovery_proof.context import RecoveryContext
from gymact.explore_recovery_proof.schedule import aba_detected
from gymact.explore_recovery_proof.strategies import RecoveryProtocol
from gymact.explore_recovery_proof.subject import Refusal, Subject

SUBJECT = Subject("o/r@" + "1" * 40)
POLICY = "a" * 64


class TestRecoveryRace(unittest.TestCase):
    def test_aba_does_not_launder_changed_generation(self):
        base = RecoveryContext(SUBJECT, "cut", "S", POLICY, 1)
        target = RecoveryContext(SUBJECT, "cut", "S", POLICY, 2)
        current = RecoveryContext(SUBJECT, "cut", "S", POLICY, 3)
        attempt = RecoveryAttempt.issue("x", 1, base, target, "CAS")
        self.assertTrue(aba_detected((base.cut_id, "other", current.cut_id)))
        with self.assertRaisesRegex(Refusal, "STALE_TARGET"):
            admit(attempt, base, target, current, RecoveryProtocol.CAS_RESELECT)
