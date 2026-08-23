import unittest
from datetime import datetime, timezone
from fractions import Fraction

from gymact.explore_counterfactual_acquisition import LoggedDecision, Subject, world
from gymact.explore_counterfactual_acquisition.diagnostics import diagnose
from gymact.explore_counterfactual_acquisition.pareto import EvaluationVector, frontier
from gymact.explore_counterfactual_acquisition.shift import total_variation
from gymact.explore_counterfactual_acquisition.strategies import OPEStrategy


class DiagnosticsParetoFailureCourt(unittest.TestCase):
    def test_diagnostics_pareto_and_seeded_world(self) -> None:
        subject = Subject("seanchatmangpt/gymact", "e" * 40)
        now = datetime(2026, 8, 23, tzinfo=timezone.utc)
        rows = (
            LoggedDecision(
                subject, "d2", "c2", "b", Fraction(1), Fraction(1, 2), Fraction(1, 4), now
            ),
            LoggedDecision(
                subject, "d1", "c1", "a", Fraction(2), Fraction(1, 2), Fraction(3, 4), now
            ),
        )
        diagnostic = diagnose(rows)
        self.assertLessEqual(diagnostic.effective_sample_ratio, 1)
        self.assertGreater(total_variation(rows), 0)
        good = EvaluationVector(
            OPEStrategy.IPS,
            Fraction(1),
            Fraction(1),
            Fraction(1),
            Fraction(1),
            Fraction(),
        )
        dominated = EvaluationVector(
            OPEStrategy.SNIPS,
            Fraction(2),
            Fraction(1, 2),
            Fraction(1, 2),
            Fraction(2),
            Fraction(1, 2),
        )
        self.assertEqual(frontier((dominated, good)), (good,))
        self.assertEqual(world(rows, seed=17), world(reversed(rows), seed=17))


if __name__ == "__main__":
    unittest.main()
