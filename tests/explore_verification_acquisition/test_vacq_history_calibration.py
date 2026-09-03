import unittest
from fractions import Fraction

from gymact.explore_verification_acquisition.calibration import calibrate
from gymact.explore_verification_acquisition.capability import RailCapability
from gymact.explore_verification_acquisition.history import (
    CalibrationTrial,
    TrialOutcome,
    admit_trials,
)
from gymact.explore_verification_acquisition.subject import Refusal, Subject


class HistoryCalibrationTest(unittest.TestCase):
    def test_exact_rates_and_duplicate_refusal(self):
        subject = Subject("o/r", "b" * 40)
        rail = RailCapability(subject, "ci", "pytest", "runtime", frozenset({"unit"}), 10, 10)
        trials = (
            CalibrationTrial(rail, "f1", TrialOutcome.DETECTED, True),
            CalibrationTrial(rail, "f2", TrialOutcome.DETECTED, True),
            CalibrationTrial(rail, "c1", TrialOutcome.CLEAN, False),
            CalibrationTrial(rail, "c2", TrialOutcome.FALSE_ALARM, False),
        )
        admitted = admit_trials(trials)
        calibration = calibrate(rail, admitted)
        self.assertEqual(calibration.detection_rate, Fraction(1))
        self.assertEqual(calibration.false_alarm_rate, Fraction(1, 2))
        self.assertEqual(calibration.state, "UNRELIABLE")
        with self.assertRaisesRegex(Refusal, "REFUSED_DUPLICATE"):
            admit_trials((*trials, trials[0]))
