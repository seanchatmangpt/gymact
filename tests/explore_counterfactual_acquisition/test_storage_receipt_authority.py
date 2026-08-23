import unittest
from fractions import Fraction

from gymact.explore_counterfactual_acquisition import Refused, Subject
from gymact.explore_counterfactual_acquisition.authority import ActionClass, admit_action
from gymact.explore_counterfactual_acquisition.receipt import issue, replay
from gymact.explore_counterfactual_acquisition.storage import StorageKind, discover, select


class StorageReceiptAuthorityCourt(unittest.TestCase):
    def test_storage_receipt_and_do_fence(self) -> None:
        self.assertEqual(len(discover()), 3)
        self.assertEqual(select(transactional=True).kind, StorageKind.SQLITE)
        subject = Subject("seanchatmangpt/gymact", "f" * 40)
        receipt = issue(
            subject=subject,
            strategy="IPS",
            estimate=Fraction(3, 2),
            standing="PARTIAL_ALIVE",
            storage="SQLITE",
        )
        self.assertTrue(replay(receipt))
        receipt.body["standing"] = "ALIVE"
        self.assertFalse(replay(receipt))
        with self.assertRaisesRegex(Refused, "REFUSED_UNRECEIPTED_ACTUATION"):
            admit_action(ActionClass.DO)


if __name__ == "__main__":
    unittest.main()
