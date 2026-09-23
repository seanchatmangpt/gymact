import unittest

from gymact.explore_ack_epoch.receipt import Receipt, make_receipt, replay


class T(unittest.TestCase):
    def test_tamper(self):
        r = make_receipt({"x": 1})
        self.assertTrue(replay(r))
        self.assertFalse(replay(Receipt({**r.payload, "x": 2}, r.digest)))
