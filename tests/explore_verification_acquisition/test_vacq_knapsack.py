import unittest

from gymact.explore_verification_acquisition.budget import AcquisitionBudget
from gymact.explore_verification_acquisition.capability import RailCapability
from gymact.explore_verification_acquisition.dependence import IndependenceProof
from gymact.explore_verification_acquisition.knapsack import select_exact
from gymact.explore_verification_acquisition.strategies import AcquisitionStrategy, Score
from gymact.explore_verification_acquisition.subject import Subject


class KnapsackTest(unittest.TestCase):
    def test_exact_budget_selection(self):
        subject = Subject("o/r", "f" * 40)
        left = RailCapability(subject, "a", "fa", "da", frozenset({"unit"}), 6, 6)
        middle = RailCapability(
            subject, "b", "fb", "db", frozenset({"integration"}), 6, 6
        )
        right = RailCapability(subject, "c", "fc", "dc", frozenset({"e2e"}), 10, 10)
        scores = {
            left.fingerprint: Score(left.fingerprint, AcquisitionStrategy.MAX_INFORMATION, 5),
            middle.fingerprint: Score(
                middle.fingerprint, AcquisitionStrategy.MAX_INFORMATION, 5
            ),
            right.fingerprint: Score(right.fingerprint, AcquisitionStrategy.MAX_INFORMATION, 7),
        }
        proofs = (
            IndependenceProof(left.fingerprint, middle.fingerprint, "ab"),
            IndependenceProof(left.fingerprint, right.fingerprint, "ac"),
            IndependenceProof(middle.fingerprint, right.fingerprint, "bc"),
        )
        selected = select_exact(
            (left, middle, right),
            scores,
            AcquisitionBudget(12, 12, 2),
            proofs,
        )
        self.assertEqual({rail.rail_id for rail in selected.rails}, {"a", "b"})
