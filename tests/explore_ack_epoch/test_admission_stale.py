import unittest
from datetime import UTC, datetime

from gymact.explore_ack_epoch.admission import admit
from gymact.explore_ack_epoch.epoch import Epoch
from gymact.explore_ack_epoch.witness import Witness


class T(unittest.TestCase):
    def test_stale(self):
        e = Epoch(3, "e", "c" * 64, datetime.now(UTC))
        w = Witness("c", 2, "e", "DELIVERY", "w", datetime.now(UTC))
        with self.assertRaisesRegex(ValueError, "STALE_INVALIDATION_EPOCH"):
            admit(e, [w])
