import unittest
from dataclasses import replace

from gymact.explore_intent_frontier.receipt import manufacture, replay


class TestReceipt(unittest.TestCase):
    def test_receipt_is_deterministic_and_tamper_sensitive(self):
        a = manufacture({"b": 2, "a": 1})
        b = manufacture({"a": 1, "b": 2})
        self.assertEqual(a.digest, b.digest)
        self.assertTrue(replay(a))
        bad = replace(a, body={**a.body, "standing": "ALIVE"})
        self.assertFalse(replay(bad))
        authority = replace(a, body={**a.body, "actuation_performed": True})
        self.assertFalse(replay(authority))


if __name__ == "__main__":
    unittest.main()
