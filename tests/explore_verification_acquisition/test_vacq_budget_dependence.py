import unittest

from gymact.explore_verification_acquisition.budget import AcquisitionBudget
from gymact.explore_verification_acquisition.capability import RailCapability
from gymact.explore_verification_acquisition.dependence import (
    Dependence,
    IndependenceProof,
    dependence,
    independent_set,
)
from gymact.explore_verification_acquisition.subject import Subject


class BudgetDependenceTest(unittest.TestCase):
    def test_budget_and_explicit_independence(self):
        subject = Subject("o/r", "c" * 40)
        left = RailCapability(subject, "a", "pytest", "runtime", frozenset({"unit"}), 10, 10)
        right = RailCapability(
            subject, "b", "pytest", "runtime", frozenset({"integration"}), 10, 10
        )
        self.assertEqual(dependence(left, right), Dependence.CORRELATED)
        proof = IndependenceProof(left.fingerprint, right.fingerprint, "proof")
        self.assertTrue(independent_set((left, right), (proof,)))
        self.assertTrue(AcquisitionBudget(25, 25, 2).admits((left, right)))
        self.assertFalse(AcquisitionBudget(15, 25, 2).admits((left, right)))
