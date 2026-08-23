import unittest
from dataclasses import replace
from fractions import Fraction

from gymact.explore_causal_sensitivity import Subject, make_receipt
from gymact.explore_causal_sensitivity.pareto import Candidate, frontier
from gymact.explore_causal_sensitivity.replay import replay


class FrontierReplayTest(unittest.TestCase):
    def test_dominated_candidate_is_removed(self) -> None:
        strong = Candidate("strong", Fraction(1, 10), Fraction(9, 10), Fraction(2))
        weak = Candidate("weak", Fraction(1, 5), Fraction(4, 5), Fraction(3, 2))
        self.assertEqual(frontier((weak, strong)), (strong,))

    def test_receipt_tamper_fails_replay(self) -> None:
        subject = Subject.parse("owner/repo@" + "b" * 40)
        receipt = make_receipt(subject, "ROBUST_IPS", "PARTIAL_ALIVE")
        digest = receipt.digest()
        self.assertTrue(replay(receipt, digest))
        self.assertFalse(replay(replace(receipt, standing="ALIVE"), digest))


if __name__ == "__main__":
    unittest.main()
