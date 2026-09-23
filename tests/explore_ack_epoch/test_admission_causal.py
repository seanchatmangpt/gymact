import unittest
from datetime import UTC, datetime

from gymact.explore_ack_epoch.admission import admit
from gymact.explore_ack_epoch.epoch import Epoch
from gymact.explore_ack_epoch.witness import Witness


class T(unittest.TestCase):
    def test_gap(self):
        t = datetime.now(UTC)
        e = Epoch(1, "e", "d" * 64, t)
        w = Witness("c", 1, "e", "ACK", "a", t, parent_id="missing")
        with self.assertRaisesRegex(ValueError, "CAUSAL_GAP"):
            admit(e, [w])
