import unittest

from gymact.explore_sequential_acquisition.authority import ActionClass, require
from gymact.explore_sequential_acquisition.receipt import AcquisitionReceipt, replay


class ReceiptAuthorityCourt(unittest.TestCase):
    def test_receipt_and_do_refusal(self):
        receipt = AcquisitionReceipt(
            "repo@" + "a" * 40,
            "p",
            "b" * 64,
            "PARTIAL_ALIVE",
            1,
        )
        digest = receipt.digest()
        self.assertTrue(replay(receipt, digest))
        changed = AcquisitionReceipt(
            receipt.subject,
            receipt.policy,
            receipt.selected_sensor,
            "UNKNOWN",
            1,
        )
        self.assertFalse(replay(changed, digest))
        with self.assertRaisesRegex(
            PermissionError,
            "REFUSED_UNRECEIPTED_ACTUATION",
        ):
            require(ActionClass.DO)


if __name__ == "__main__":
    unittest.main()
