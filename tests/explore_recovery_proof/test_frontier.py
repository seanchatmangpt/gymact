import unittest

from gymact.explore_recovery_proof.attempt import RecoveryAttempt
from gymact.explore_recovery_proof.context import RecoveryContext
from gymact.explore_recovery_proof.frontier import resolve
from gymact.explore_recovery_proof.subject import Refusal, Subject

SUBJECT = Subject("o/r@" + "1" * 40)
POLICY = "a" * 64


class TestFrontier(unittest.TestCase):
    def test_history_preserved(self):
        context = RecoveryContext(SUBJECT, "c", "S", POLICY, 1)
        old = RecoveryAttempt.issue("a", 1, context, context, "x")
        current = RecoveryAttempt.issue("b", 2, context, context, "x")
        frontier = resolve([old, current])
        self.assertEqual(frontier.current.identity, current.identity)
        self.assertEqual(len(frontier.historical), 1)

    def test_divergent_maxima_refuse(self):
        context = RecoveryContext(SUBJECT, "c", "S", POLICY, 1)
        attempts = [
            RecoveryAttempt.issue("a", 2, context, context, "x"),
            RecoveryAttempt.issue("b", 2, context, context, "x"),
        ]
        with self.assertRaisesRegex(Refusal, "DIVERGENT"):
            resolve(attempts)
