import unittest
from dataclasses import replace

from gymact.explore_verification_acquisition.receipt import (
    AcquisitionReceipt,
    ActionClass,
    replay,
    require,
)
from gymact.explore_verification_acquisition.subject import Refusal, Subject


class ReceiptTest(unittest.TestCase):
    def test_replay_and_do_refusal(self):
        receipt = AcquisitionReceipt(
            Subject("o/r", "3" * 40),
            "S",
            ("a",),
            "MEMORY",
            "REQUALIFYING",
        )
        self.assertTrue(replay(receipt, receipt.digest))
        self.assertFalse(replay(replace(receipt, standing="UNKNOWN"), receipt.digest))
        with self.assertRaisesRegex(Refusal, "REFUSED_UNRECEIPTED_ACTUATION"):
            require(ActionClass.DO)
