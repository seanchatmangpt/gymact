import unittest

from gymact.explore_recovery_proof.attempt import RecoveryAttempt
from gymact.explore_recovery_proof.authority import ActionClass, require
from gymact.explore_recovery_proof.context import RecoveryContext
from gymact.explore_recovery_proof.engine import qualify
from gymact.explore_recovery_proof.receipt import replay
from gymact.explore_recovery_proof.strategies import RecoveryProtocol
from gymact.explore_recovery_proof.subject import Refusal, Subject
from gymact.explore_recovery_proof.topology import DependencyGraph

SUBJECT = Subject("o/r@" + "1" * 40)
POLICY = "a" * 64


class TestE2E(unittest.TestCase):
    def test_current_recovery_constructs_requalifying_receipt_without_do(self):
        base = RecoveryContext(SUBJECT, "old", "LATEST", POLICY, 1)
        target = RecoveryContext(SUBJECT, "new", "LATEST", POLICY, 2)
        attempt = RecoveryAttempt.issue("r1", 1, base, target, "CAS_RESELECT")
        graph = DependencyGraph({SUBJECT.identity: ()})
        qualification = qualify(
            attempt=attempt,
            base=base,
            target=target,
            current=target,
            protocol=RecoveryProtocol.CAS_RESELECT,
            dependency_graph=graph,
            standings={SUBJECT.identity: "PARTIAL_ALIVE"},
            transactional=True,
        )
        self.assertEqual(qualification.standing, "REQUALIFYING")
        self.assertTrue(replay(qualification.receipt))
        self.assertFalse(qualification.receipt.body["actuation_performed"])
        with self.assertRaisesRegex(Refusal, "UNRECEIPTED_ACTUATION"):
            require(ActionClass.DO)
