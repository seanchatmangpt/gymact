import unittest

from gymact.explore_robustness_bound_calibration import (
    Receipt,
    Refused,
    Subject,
    replay,
    require_action,
)


class ReceiptCourt(unittest.TestCase):
    def test_tamper_and_do_refuse(self) -> None:
        subject = Subject("seanchatmangpt/gymact@" + "a" * 40)
        receipt = Receipt.create(subject, "b" * 64, "PARTIAL_ALIVE")
        self.assertTrue(replay(receipt, receipt.digest))
        self.assertFalse(replay(receipt, "0" * 64))
        with self.assertRaises(Refused):
            require_action("DO")


if __name__ == "__main__":
    unittest.main()
