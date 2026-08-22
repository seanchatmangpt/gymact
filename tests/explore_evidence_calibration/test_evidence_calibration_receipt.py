import unittest
from gymact.explore_evidence_calibration.receipt import QualificationReceipt,issue,replay
class ReceiptTests(unittest.TestCase):
    def test_tamper_and_actuation_fail_replay(self):
        receipt=issue({"subject":"o/r@"+"a"*40,"standing":"UNKNOWN"}); self.assertTrue(replay(receipt))
        payload=dict(receipt.payload); payload["actuation_performed"]=True
        self.assertFalse(replay(QualificationReceipt(payload,receipt.digest)))
