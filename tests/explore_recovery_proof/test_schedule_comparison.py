import unittest

from gymact.explore_recovery_proof.comparison import pareto
from gymact.explore_recovery_proof.schedule import aba_detected, deterministic_interleaving
from gymact.explore_recovery_proof.strategies import RecoveryProtocol


class TestScheduleComparison(unittest.TestCase):
    def test_seeded_interleaving_replays(self):
        left = deterministic_interleaving(7, ("a", "b"))
        right = deterministic_interleaving(7, ("a", "b"))
        self.assertEqual(left, right)

    def test_aba_and_pareto_are_explicit(self):
        self.assertTrue(aba_detected(("A", "B", "A")))
        protocols = {score.protocol for score in pareto()}
        self.assertIn(RecoveryProtocol.CAS_RESELECT, protocols)
        self.assertIn(RecoveryProtocol.VALIDATE_REBIND, protocols)
