import unittest
from fractions import Fraction

from gymact.explore_realized_acquisition_feedback.calibration import GainCalibration
from gymact.explore_realized_acquisition_feedback.engine import construct_feedback_plan
from gymact.explore_realized_acquisition_feedback.policies import FeedbackPolicy
from gymact.explore_realized_acquisition_feedback.receipt import replay
from gymact.explore_realized_acquisition_feedback.subject import Subject


class TestChicago(unittest.TestCase):
    def test_closed_loop_remains_non_actuating(self):
        subject = Subject("seanchatmangpt/gymact", "0" * 40)
        plan, receipt = construct_feedback_plan(
            subject,
            GainCalibration(4, Fraction(0), Fraction(1, 10)),
            True,
            Fraction(1, 5),
            FeedbackPolicy.EXPLORE_DRIFT,
        )
        self.assertEqual(plan.standing, "REQUALIFYING")
        self.assertFalse(receipt.actuation_performed)
        self.assertTrue(replay(receipt, receipt.digest()))
