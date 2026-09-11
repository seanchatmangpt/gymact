import unittest
from dataclasses import replace

from gymact.explore_replicated_projection_quorum.receipt import (
    ActionClass,
    QualificationReceipt,
    replay,
    require_action,
)
from gymact.explore_replicated_projection_quorum.refusal import Refused


class ReceiptAuthorityCourt(unittest.TestCase):
    def test_receipt_tamper_and_direct_do_fail_closed(self):
        receipt = QualificationReceipt.create({"standing": "PARTIAL_ALIVE"})
        self.assertTrue(replay(receipt))
        tampered = replace(receipt, body={**receipt.body, "standing": "ALIVE"})
        self.assertFalse(replay(tampered))
        with self.assertRaisesRegex(Refused, "REFUSED_UNRECEIPTED_ACTUATION"):
            require_action(ActionClass.DO)


if __name__ == "__main__":
    unittest.main()
