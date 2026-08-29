import unittest

from gymact.explore_process_transition_correspondence.identity import Refused, Subject
from gymact.explore_process_transition_correspondence.runtime_receipt import RuntimeReceipt, admit_runtime_receipt


class RuntimeReceiptCourt(unittest.TestCase):
    def test_tls_contradiction_refuses(self) -> None:
        subject = Subject.parse("o/r@" + "a" * 40)
        bad = RuntimeReceipt(subject, "peer over inet_tls", "inet_tcp", False, 0)
        with self.assertRaisesRegex(Refused, "TLS_RECEIPT_TRANSPORT_CONTRADICTION"):
            admit_runtime_receipt(bad)
        good = RuntimeReceipt(subject, "peer over inet_tls", "inet_tls", True, 0)
        self.assertEqual(admit_runtime_receipt(good, require_tls=True), good)


if __name__ == "__main__":
    unittest.main()
