import unittest

from gymact.explore_process_trace_correspondence.authority import ActionClass, admit
from gymact.explore_process_trace_correspondence.receipt import Receipt, replay
from gymact.explore_process_trace_correspondence.refusal import Refused
from gymact.explore_process_trace_correspondence.standing import Standing
from gymact.explore_process_trace_correspondence.subject import Subject


class AuthorityReceiptCourt(unittest.TestCase):
    def test_do_refusal_and_replay(self):
        subject = Subject("owner/repo@" + "f" * 40)
        with self.assertRaises(Refused):
            admit(ActionClass.DO)
        receipt = Receipt(subject, "exact", Standing.PARTIAL_ALIVE)
        digest = receipt.digest()
        self.assertTrue(replay(receipt, digest))
        self.assertFalse(replay(receipt, "0" * 64))
        with self.assertRaises(Refused):
            Receipt(subject, "exact", Standing.PARTIAL_ALIVE, True).digest()


if __name__ == "__main__": unittest.main()
