from datetime import datetime, timezone
from fractions import Fraction
import unittest
from gymact.explore_process_convergence_correspondence import ClosureEpoch, DependencyGraph, ObligationState, Standing, State, Strategy, SubjectEpoch, Trajectory, qualify, replay

class TestChicagoResidualFailure(unittest.TestCase):
    def test_reactor_discharge_does_not_launder_broad_ci_failure(self) -> None:
        first = ClosureEpoch(SubjectEpoch("seanchatmangpt/gymact@" + "a" * 40, 0), datetime(2026, 8, 23, 9, tzinfo=timezone.utc), (ObligationState("reactor", State.FAIL, Fraction(1)), ObligationState("broad_ci", State.FAIL, Fraction(2))))
        second = ClosureEpoch(SubjectEpoch("seanchatmangpt/gymact@" + "b" * 40, 1), datetime(2026, 8, 23, 9, 1, tzinfo=timezone.utc), (ObligationState("reactor", State.PASS, Fraction(1)), ObligationState("broad_ci", State.FAIL, Fraction(2))))
        result = qualify(Trajectory((first, second)), DependencyGraph({}), Strategy.LYAPUNOV)
        self.assertEqual(result.standing, Standing.BUILD_BROKEN)
        self.assertTrue(replay(result.receipt))
        self.assertFalse(result.receipt.body["actuation_performed"])
