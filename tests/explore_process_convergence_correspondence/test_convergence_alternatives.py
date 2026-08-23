from datetime import datetime, timezone
from fractions import Fraction
import unittest
from gymact.explore_process_convergence_correspondence import ClosureEpoch, Direction, ObligationState, State, Strategy, SubjectEpoch, Trajectory, classify
from gymact.explore_process_convergence_correspondence.potential import max_severity, weighted_l1

class TestConvergenceAlternatives(unittest.TestCase):
    def test_potentials_and_strategy_are_noncollapsed(self) -> None:
        a = ClosureEpoch(SubjectEpoch("seanchatmangpt/gymact@" + "a" * 40, 0), datetime(2026, 8, 23, 9, tzinfo=timezone.utc), (ObligationState("x", State.FAIL, Fraction(1)), ObligationState("y", State.PASS, Fraction(3))))
        b = ClosureEpoch(SubjectEpoch("seanchatmangpt/gymact@" + "b" * 40, 1), datetime(2026, 8, 23, 9, 1, tzinfo=timezone.utc), (ObligationState("x", State.BLOCKED, Fraction(1)), ObligationState("y", State.PASS, Fraction(3))))
        self.assertNotEqual(weighted_l1(a), max_severity(a))
        self.assertEqual(classify(Trajectory((a, b)), Strategy.POTENTIAL), Direction.CONVERGING)
