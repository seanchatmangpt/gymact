import unittest
from datetime import datetime, timezone

from gymact.explore_epoch.admission import admit
from gymact.explore_epoch.epoch import InvalidationEpoch
from gymact.explore_epoch.identity import Subject
from gymact.explore_epoch.witness import Witness, WitnessKind


class TestEpochCausality(unittest.TestCase):
    def test_gap_refused(self):
        producer = Subject("o/p", "a" * 40)
        consumer = Subject("o/c", "b" * 40)
        now = datetime.now(timezone.utc)
        epoch = InvalidationEpoch(producer, 1, "e", "c" * 64, now)
        witness = Witness(
            consumer, 1, "e", WitnessKind.ACKNOWLEDGED, 2, now, parent_sequence=1
        )
        with self.assertRaisesRegex(ValueError, "REFUSED_CAUSAL_WITNESS_GAP"):
            admit(epoch, (consumer,), (witness,))


if __name__ == "__main__":
    unittest.main()
