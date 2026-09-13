import unittest
from datetime import datetime, timezone

from gymact.explore_epoch.epoch import InvalidationEpoch
from gymact.explore_epoch.identity import Subject


class TestEpochContract(unittest.TestCase):
    def test_generation_bounds(self):
        with self.assertRaisesRegex(ValueError, "REFUSED_NEGATIVE_EPOCH"):
            InvalidationEpoch(
                Subject("o/r", "a" * 40), -1, "e", "b" * 64, datetime.now(timezone.utc)
            )


if __name__ == "__main__":
    unittest.main()
