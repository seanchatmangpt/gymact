import unittest

from world import PROJECTION, UNIVERSE, projection

from gymact.explore_replicated_projection_quorum.quorum import QuorumState, assess_quorum


class QuorumCourt(unittest.TestCase):
    def test_majority_and_split_brain_are_distinct(self):
        healthy = assess_quorum(tuple(projection(r) for r in ("r1", "r2", "r3")), UNIVERSE)
        self.assertIs(healthy.state, QuorumState.HEALTHY)
        self.assertEqual(healthy.standing, "PARTIAL_ALIVE")
        split = assess_quorum(
            (
                projection("r1"),
                projection("r2", digest="c" * 64),
                projection("r3", digest=PROJECTION),
            ),
            UNIVERSE,
        )
        self.assertIs(split.state, QuorumState.SPLIT_BRAIN)
        self.assertEqual(split.standing, "BLOCKED")


if __name__ == "__main__":
    unittest.main()
