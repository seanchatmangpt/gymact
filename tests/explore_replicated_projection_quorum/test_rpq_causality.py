import unittest

from gymact.explore_replicated_projection_quorum.causality import causal_profile

from .world import projection


class CausalityCourt(unittest.TestCase):
    def test_concurrency_remains_topology(self):
        items = (
            projection("r1", clock={"r1": 2, "r2": 0}),
            projection("r2", clock={"r1": 0, "r2": 2}),
        )
        profile = causal_profile(items)
        self.assertEqual(profile.concurrent_pairs, 1)
        self.assertEqual(set(profile.maximal_replica_ids), {"r1", "r2"})


if __name__ == "__main__":
    unittest.main()
