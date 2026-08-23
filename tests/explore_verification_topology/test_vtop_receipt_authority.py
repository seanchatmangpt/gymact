import unittest
from gymact.explore_verification_topology.subject import Refusal, Subject
from gymact.explore_verification_topology.receipt import QualificationReceipt, replay
from gymact.explore_verification_topology.engine import ActionClass, require

class TestReceiptAuthority(unittest.TestCase):
    def test_replay_and_tamper(self):
        receipt = QualificationReceipt(Subject("o/r", "a" * 40), "IMPORTLIB", "PARTIAL_ALIVE", "JSONL", 2, False)
        digest = receipt.digest()
        self.assertTrue(replay(receipt, digest))
        tampered = QualificationReceipt(receipt.subject, receipt.policy, receipt.standing, receipt.store, 3, False)
        self.assertFalse(replay(tampered, digest))

    def test_do_refused(self):
        with self.assertRaisesRegex(Refusal, "UNRECEIPTED_ACTUATION"):
            require(ActionClass.DO)
