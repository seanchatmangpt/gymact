import unittest
from datetime import datetime, timezone

from gymact.explore_epoch.admission import admit
from gymact.explore_epoch.epoch import InvalidationEpoch
from gymact.explore_epoch.identity import Subject
from gymact.explore_epoch.witness import Witness, WitnessKind


class TestEpochAdmission(unittest.TestCase):
    def test_stale_generation_refused(self):
        producer = Subject("o/p", "a" * 40)
        consumer = Subject("o/c", "b" * 40)
        epoch = InvalidationEpoch(producer, 3, "e", "c" * 64, datetime.now(timezone.utc))
        witness = Witness(
            consumer, 2, "e", WitnessKind.DELIVERED, 1, datetime.now(timezone.utc)
        )
        with self.assertRaisesRegex(ValueError, "REFUSED_STALE_INVALIDATION_EPOCH"):
            admit(epoch, (consumer,), (witness,))


if __name__ == "__main__":
    unittest.main()
