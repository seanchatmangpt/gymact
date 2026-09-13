import unittest
from dataclasses import replace

from gymact.explore_rail_consensus.receipt import ActionClass, QualificationReceipt, replay, require
from gymact.explore_rail_consensus.subject import Refusal, Subject


class ReceiptAuthorityTest(unittest.TestCase):
    def test_tamper_and_do_refusal(self):
        receipt = QualificationReceipt(Subject("o/r", "1" * 40), "S", "UNKNOWN", 1, "MEMORY")
        self.assertTrue(replay(receipt, receipt.digest))
        self.assertFalse(replay(replace(receipt, standing="PARTIAL_ALIVE"), receipt.digest))
        with self.assertRaisesRegex(Refusal, "REFUSED_UNRECEIPTED_ACTUATION"):
            require(ActionClass.DO)
