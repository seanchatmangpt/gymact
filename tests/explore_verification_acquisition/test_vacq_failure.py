import unittest

from gymact.explore_verification_acquisition.failure import FailureWorld


class FailureWorldTest(unittest.TestCase):
    def test_common_mode_and_flake_replay(self):
        world = FailureWorld(42, 0.5, 0.5)
        first = world.inject(("pytest", "world", "pytest"), ("a", "b", "c"))
        second = world.inject(("pytest", "world", "pytest"), ("a", "b", "c"))
        self.assertEqual(first, second)
