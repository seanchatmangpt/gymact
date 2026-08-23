import unittest

from gymact.explore_robustness_bound_calibration import IndependenceProof, Refused


class IndependenceCourt(unittest.TestCase):
    def test_shared_model_refuses(self) -> None:
        proof = IndependenceProof("a" * 64, "b" * 64, "impl-a", "impl-b", "c" * 64)
        proof.require()
        with self.assertRaises(Refused):
            IndependenceProof("a" * 64, "a" * 64, "impl-a", "impl-b", "c" * 64).require()


if __name__ == "__main__":
    unittest.main()
