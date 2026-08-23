import unittest
from fractions import Fraction

from gymact.explore_sequential_acquisition.belief import BeliefState
from gymact.explore_sequential_acquisition.budget import Budget
from gymact.explore_sequential_acquisition.engine import construct_plan
from gymact.explore_sequential_acquisition.policy import Policy
from gymact.explore_sequential_acquisition.sensor import SensorCapability
from gymact.explore_sequential_acquisition.strategy import CandidateScore, Strategy


class ChicagoCourt(unittest.TestCase):
    def test_constructs_bounded_non_actuating_plan(self):
        sensor = SensorCapability("s", "family", "domain", 1, "a" * 64, Fraction(1), 10)
        belief = BeliefState(
            ("healthy", "fault"),
            (Fraction(1, 2), Fraction(1, 2)),
        )
        policy = Policy("info", Strategy.MAX_INFORMATION, 3)
        scores = {
            sensor.digest: CandidateScore(
                sensor.digest,
                Fraction(3, 4),
                Fraction(1),
                Fraction(0),
                Fraction(1, 4),
                Fraction(1),
            )
        }
        plan = construct_plan(
            subject="seanchatmangpt/gymact@" + "b" * 40,
            belief=belief,
            policy=policy,
            candidates=(sensor,),
            scores=scores,
            budget=Budget(Fraction(2), 20, 2),
            step=1,
        )
        self.assertEqual(plan.selected_sensor, sensor.digest)
        self.assertEqual(plan.receipt.standing, "PARTIAL_ALIVE")
        self.assertFalse(plan.receipt.actuation_performed)
        self.assertEqual(plan.remaining_budget.samples, 1)


if __name__ == "__main__":
    unittest.main()
