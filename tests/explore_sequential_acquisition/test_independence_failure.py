import unittest
from fractions import Fraction
from gymact.explore_sequential_acquisition.failure import FailureWorld
from gymact.explore_sequential_acquisition.independence import IndependenceProof, independent
from gymact.explore_sequential_acquisition.sensor import SensorCapability


class IndependenceFailureCourt(unittest.TestCase):
    def test_independence_and_failure_replay(self):
        left = SensorCapability("l", "f", "d", 1, "a" * 64, Fraction(1), 10)
        right = SensorCapability("r", "f", "d", 1, "b" * 64, Fraction(1), 10)
        self.assertFalse(independent(left, right))
        proof = IndependenceProof(left.digest, right.digest, "separate physical channels")
        self.assertTrue(independent(left, right, proof))
        world = FailureWorld(7, 0.5, 0.5)
        self.assertEqual(world.failed(("b", "a")), world.failed(("a", "b")))


if __name__ == "__main__":
    unittest.main()
