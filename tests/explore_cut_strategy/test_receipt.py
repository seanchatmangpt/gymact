import unittest
from gymact.explore_cut_strategy.receipt import QualificationReceipt,replay
class T(unittest.TestCase):
    def test_tamper(self):
        r=QualificationReceipt("s","c","LATEST_COMPLETE","MEMORY","PARTIAL_ALIVE")
        d=r.digest(); self.assertTrue(replay(r,d))
        self.assertFalse(replay(QualificationReceipt("s","x","LATEST_COMPLETE","MEMORY","PARTIAL_ALIVE"),d))
