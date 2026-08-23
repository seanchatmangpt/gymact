import unittest
from datetime import datetime, timezone
from fractions import Fraction

from gymact.explore_counterfactual_acquisition import LoggedDecision, ModelPrediction, Subject, qualify, replay


class ChicagoCourt(unittest.TestCase):
    def test_bounded_logged_evaluation(self) -> None:
        subject = Subject("seanchatmangpt/gymact", "1" * 40)
        now = datetime(2026, 8, 23, tzinfo=timezone.utc)
        rows = (
            LoggedDecision(subject, "d1", "c1", "a", Fraction(3), Fraction(1, 2), Fraction(1, 2), now),
            LoggedDecision(subject, "d2", "c2", "b", Fraction(2), Fraction(1, 2), Fraction(1, 2), now),
            LoggedDecision(subject, "d3", "c3", "a", Fraction(4), Fraction(1, 2), Fraction(1, 2), now),
        )
        predictions = tuple(ModelPrediction(row.decision_id, row.realized_gain, "2" * 64) for row in rows)
        result = qualify(subject=subject, decisions=rows, predictions=predictions, transactional=True)
        self.assertEqual(result.standing, "PARTIAL_ALIVE")
        self.assertEqual(len(result.alternatives), 5)
        self.assertFalse(result.actuation_performed)
        self.assertTrue(replay(result.receipt))


if __name__ == "__main__":
    unittest.main()
