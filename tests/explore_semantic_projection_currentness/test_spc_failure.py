import unittest

from gymact.explore_semantic_projection_currentness.currentness import ProjectionEpoch
from gymact.explore_semantic_projection_currentness.failure import seeded_projection_drift
from gymact.explore_semantic_projection_currentness.subject import Subject
from tests.explore_semantic_projection_currentness._fixtures import DIGEST, SHA, fixtures


class Court(unittest.TestCase):
    def test_seeded_drift_is_replayable(self):
        semantic_type, *_ = fixtures()
        epoch = ProjectionEpoch(
            Subject("seanchatmangpt/gymact", SHA),
            1,
            DIGEST,
            "b" * 64,
        )
        first = seeded_projection_drift(semantic_type, epoch, seed=73)
        second = seeded_projection_drift(semantic_type, epoch, seed=73)
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
