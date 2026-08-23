import unittest

from gymact.explore_replicated_projection_quorum.failure import FailureKind, inject_failure

from .world import projection


class FailureCourt(unittest.TestCase):
    def test_seeded_failure_world_replays(self):
        observations = tuple(projection(r) for r in ("r1", "r2", "r3"))
        for kind in FailureKind:
            self.assertEqual(
                inject_failure(observations, kind, 17), inject_failure(observations, kind, 17)
            )


if __name__ == "__main__":
    unittest.main()
