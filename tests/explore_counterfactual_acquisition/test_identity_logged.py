import unittest
from datetime import datetime, timezone
from fractions import Fraction

from gymact.explore_counterfactual_acquisition import LoggedDecision, Refused, Subject


class IdentityLoggedCourt(unittest.TestCase):
    def test_exact_subject_and_logged_identity(self) -> None:
        subject = Subject.parse("seanchatmangpt/gymact@" + "a" * 40)
        row = LoggedDecision(
            subject=subject,
            decision_id="d1",
            context_id="c1",
            action="sensor-a",
            realized_gain=Fraction(1, 2),
            behavior_probability=Fraction(1, 2),
            target_probability=Fraction(3, 4),
            observed_at=datetime(2026, 8, 23, tzinfo=timezone.utc),
        )
        self.assertEqual(row.subject.exact, "seanchatmangpt/gymact@" + "a" * 40)
        with self.assertRaisesRegex(Refused, "REFUSED_INEXACT_SUBJECT"):
            Subject("seanchatmangpt/gymact", "abc")
        with self.assertRaisesRegex(Refused, "REFUSED_ZERO_BEHAVIOR_PROPENSITY"):
            LoggedDecision(
                subject=subject,
                decision_id="d2",
                context_id="c1",
                action="sensor-b",
                realized_gain=Fraction(1, 3),
                behavior_probability=Fraction(),
                target_probability=Fraction(1, 2),
                observed_at=datetime(2026, 8, 23, tzinfo=timezone.utc),
            )


if __name__ == "__main__":
    unittest.main()
