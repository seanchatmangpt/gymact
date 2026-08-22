import unittest

from gymact.explore_recovery_proof.authority import ActionClass, require
from gymact.explore_recovery_proof.receipt import Receipt, issue, replay
from gymact.explore_recovery_proof.subject import Refusal


class TestReceiptAuthority(unittest.TestCase):
    def test_receipt_replay_is_tamper_sensitive(self):
        receipt = issue({"x": 1})
        self.assertTrue(replay(receipt))
        self.assertFalse(replay(Receipt({**receipt.body, "x": 2}, receipt.digest)))

    def test_direct_do_refuses(self):
        with self.assertRaisesRegex(Refusal, "UNRECEIPTED_ACTUATION"):
            require(ActionClass.DO)
