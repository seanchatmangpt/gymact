import unittest
from fractions import Fraction

from gymact.explore_sequential_acquisition.budget import Budget
from gymact.explore_sequential_acquisition.subject import Subject


class SubjectBudgetCourt(unittest.TestCase):
    def test_exact_subject_and_budget(self):
        subject = Subject("seanchatmangpt/gymact", "a" * 40)
        self.assertEqual(subject.identity, f"seanchatmangpt/gymact@{'a' * 40}")
        budget = Budget(Fraction(3, 2), 100, 2)
        remaining = budget.consume(cost=Fraction(1, 2), latency_ms=25)
        self.assertEqual(remaining.cost, Fraction(1))
        with self.assertRaisesRegex(ValueError, "REFUSED_BUDGET_EXCEEDED"):
            budget.consume(cost=Fraction(2), latency_ms=25)
        with self.assertRaisesRegex(ValueError, "REFUSED_INEXACT_SUBJECT"):
            Subject("gymact", "abc")


if __name__ == "__main__":
    unittest.main()
