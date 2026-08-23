import unittest
from fractions import Fraction

from gymact.explore_sequential_acquisition.belief import BeliefState
from gymact.explore_sequential_acquisition.stopping import StopRule
from gymact.explore_sequential_acquisition.storage import (
    StorageKind,
    StorageNeed,
    discover_storage,
    select_storage,
)


class StoppingStorageCourt(unittest.TestCase):
    def test_stopping_and_storage(self):
        belief = BeliefState(
            ("a", "b"),
            (Fraction(9, 10), Fraction(1, 10)),
        )
        self.assertTrue(StopRule(Fraction(4, 5), 5).should_stop(belief, 1))
        self.assertEqual(
            select_storage(StorageNeed(transactional=True)),
            StorageKind.SQLITE,
        )
        self.assertEqual(
            set(discover_storage()),
            {StorageKind.MEMORY, StorageKind.JSONL, StorageKind.SQLITE},
        )


if __name__ == "__main__":
    unittest.main()
