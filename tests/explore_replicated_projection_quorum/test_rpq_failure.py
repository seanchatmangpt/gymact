import unittest

from gymact.explore_replicated_projection_quorum.failure import FailureKind, inject_failure
from tests.explore_replicated_projection_quorum.world import projection


class FailureCourt(unittest.TestCase):
    def test_seeded_failure_world_replays(self):
        observations = tuple(projection(replica) for replica in ("r1", "r2", "r3"))
        for kind in FailureKind:
            first = inject_failure(observations, kind, 17)
            second = inject_failure(observations, kind, 17)
            self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
