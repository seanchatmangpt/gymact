import unittest

from gymact.explore_realized_acquisition_feedback.authority import (
    ActionClass,
    require_action,
)
from gymact.explore_realized_acquisition_feedback.receipt import FeedbackReceipt, replay
from gymact.explore_realized_acquisition_feedback.subject import Refusal


class TestReceiptAuthority(unittest.TestCase):
    def test_tamper_and_do_refusal(self):
        receipt = FeedbackReceipt("r@" + "a" * 40, "HOLD", "PARTIAL_ALIVE")
        self.assertTrue(replay(receipt, receipt.digest()))
        tampered = FeedbackReceipt(receipt.subject, receipt.policy, "ALIVE")
        self.assertFalse(replay(tampered, receipt.digest()))
        with self.assertRaisesRegex(Refusal, "REFUSED_UNRECEIPTED_ACTUATION"):
            require_action(ActionClass.DO)
