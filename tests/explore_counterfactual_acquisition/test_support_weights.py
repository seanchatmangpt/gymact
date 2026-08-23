import unittest
from datetime import datetime, timezone
from fractions import Fraction

from gymact.explore_counterfactual_acquisition import LoggedDecision, Refused, Subject
from gymact.explore_counterfactual_acquisition.support import (
    require_target_action_support,
    summarize,
)
from gymact.explore_counterfactual_acquisition.weights import (
    clipped_weight,
    importance_weight,
)


class SupportWeightsCourt(unittest.TestCase):
    def setUp(self) -> None:
        subject = Subject("seanchatmangpt/gymact", "b" * 40)
        self.rows = (
            LoggedDecision(
                subject,
                "d1",
                "c1",
                "a",
                Fraction(2),
                Fraction(1, 2),
                Fraction(3, 4),
                datetime(2026, 8, 23, tzinfo=timezone.utc),
            ),
            LoggedDecision(
                subject,
                "d2",
                "c2",
                "b",
                Fraction(1),
                Fraction(1, 2),
                Fraction(1, 4),
                datetime(2026, 8, 23, tzinfo=timezone.utc),
            ),
        )

    def test_support_and_exact_weights(self) -> None:
        self.assertEqual(importance_weight(self.rows[0]), Fraction(3, 2))
        self.assertEqual(clipped_weight(self.rows[0], Fraction(1)), Fraction(1))
        self.assertEqual(summarize(self.rows).support_ratio, Fraction(1))
        require_target_action_support(("a", "b"), ("a",))
        with self.assertRaisesRegex(Refused, "REFUSED_TARGET_ACTION_OUT_OF_SUPPORT"):
            require_target_action_support(("a",), ("a", "b"))


if __name__ == "__main__":
    unittest.main()
