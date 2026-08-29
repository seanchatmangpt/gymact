from datetime import datetime, timezone
from fractions import Fraction
import unittest
from gymact.explore_process_convergence_correspondence import ClosureEpoch, ObligationState, Refused, State, SubjectEpoch, Trajectory

BASE = "seanchatmangpt/gymact@" + "a" * 40

class TestTrajectoryInvariants(unittest.TestCase):
    def test_inexact_subject_and_universe_drift_refuse(self) -> None:
        with self.assertRaises(Refused):
            SubjectEpoch("gymact@abc", 0)
        first = ClosureEpoch(SubjectEpoch(BASE, 0), datetime(2026, 8, 23, 9, tzinfo=timezone.utc), (ObligationState("a", State.FAIL, Fraction(1)),))
        second = ClosureEpoch(SubjectEpoch("seanchatmangpt/gymact@" + "b" * 40, 1), datetime(2026, 8, 23, 9, 1, tzinfo=timezone.utc), (ObligationState("b", State.PASS, Fraction(1)),))
        with self.assertRaises(Refused):
            Trajectory((first, second))
