import unittest
from datetime import UTC, datetime

from gymact.explore_ack_epoch.census import census
from gymact.explore_ack_epoch.witness import Witness


class T(unittest.TestCase):
    def test_states(self):
        t = datetime.now(UTC)
        ws = (Witness("c", 1, "e", "DELIVERY", "d", t),)
        self.assertEqual(census(["c", "x"], ws), {"c": "DELIVERED", "x": "PENDING"})
