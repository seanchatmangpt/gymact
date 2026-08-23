import unittest

from gymact.explore_realized_acquisition_feedback.failure_world import (
    build_failure_world,
)


class TestFailureWorld(unittest.TestCase):
    def test_seed_replays(self):
        sensors = ["a", "b", "c", "d"]
        forward = build_failure_world(sensors, 7)
        reversed_world = build_failure_world(list(reversed(sensors)), 7)
        self.assertEqual(forward, reversed_world)
