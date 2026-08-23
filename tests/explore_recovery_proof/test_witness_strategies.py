import unittest

from gymact.explore_recovery_proof.attempt import RecoveryAttempt
from gymact.explore_recovery_proof.context import RecoveryContext
from gymact.explore_recovery_proof.strategies import RecoveryProtocol, decide
from gymact.explore_recovery_proof.subject import Refusal, Subject
from gymact.explore_recovery_proof.witness import CompatibilityWitness, WitnessKind

SUBJECT = Subject("o/r@" + "1" * 40)
POLICY = "a" * 64


class TestWitnessStrategies(unittest.TestCase):
    def test_three_protocols_remain_distinct(self):
        before = RecoveryContext(SUBJECT, "a", "S", POLICY, 1)
        after = RecoveryContext(SUBJECT, "b", "S", POLICY, 2)
        attempt = RecoveryAttempt.issue("x", 1, before, after, "x")
        self.assertTrue(decide(RecoveryProtocol.CAS_RESELECT, attempt, after).admissible)
        self.assertTrue(decide(RecoveryProtocol.REQUALIFY_ONLY, attempt, before).admissible)
        self.assertFalse(decide(RecoveryProtocol.VALIDATE_REBIND, attempt, after).admissible)

    def test_false_exact_witness_refuses(self):
        with self.assertRaisesRegex(Refusal, "FALSE_EXACT"):
            CompatibilityWitness(WitnessKind.EXACT, "a" * 64, "b" * 64, "c" * 64)
