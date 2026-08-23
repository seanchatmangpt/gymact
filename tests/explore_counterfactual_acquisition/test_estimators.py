import unittest
from datetime import datetime, timezone
from fractions import Fraction

from gymact.explore_counterfactual_acquisition import LoggedDecision, ModelPrediction, Subject
from gymact.explore_counterfactual_acquisition.strategies import OPEStrategy, evaluate


class EstimatorDifferentialCourt(unittest.TestCase):
    def test_five_estimators_remain_distinct(self) -> None:
        subject = Subject("seanchatmangpt/gymact", "c" * 40)
        now = datetime(2026, 8, 23, tzinfo=timezone.utc)
        rows = (
            LoggedDecision(
                subject, "d1", "c1", "a", Fraction(4), Fraction(1, 4), Fraction(3, 4), now
            ),
            LoggedDecision(
                subject, "d2", "c2", "b", Fraction(1), Fraction(3, 4), Fraction(1, 4), now
            ),
        )
        predictions = (
            ModelPrediction("d1", Fraction(3), "d" * 64),
            ModelPrediction("d2", Fraction(2), "d" * 64),
        )
        values = {
            strategy: evaluate(
                strategy,
                rows,
                predictions=predictions,
                clip=Fraction(2),
            )
            for strategy in OPEStrategy
        }
        self.assertEqual(len(set(values.values())), 5)


if __name__ == "__main__":
    unittest.main()
