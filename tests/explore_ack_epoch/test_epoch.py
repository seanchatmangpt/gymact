import unittest
from datetime import UTC, datetime

from gymact.explore_ack_epoch.epoch import Epoch


class T(unittest.TestCase):
    def test_epoch(self):
        Epoch(2, "e", "b" * 64, datetime.now(UTC))
        with self.assertRaisesRegex(ValueError, "INVALID_EPOCH"):
            Epoch(-1, "e", "b" * 64, datetime.now(UTC))
