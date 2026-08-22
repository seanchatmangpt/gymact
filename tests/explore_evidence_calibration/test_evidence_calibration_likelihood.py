import unittest
from datetime import UTC, datetime

from gymact.explore_evidence_calibration.contracts import Subject
from gymact.explore_evidence_calibration.estimate import estimate
from gymact.explore_evidence_calibration.likelihood import contribution
from gymact.explore_evidence_calibration.trials import CalibrationTrial
from gymact.explore_evidence_calibration.witness import CurrentWitness


class LikelihoodTests(unittest.TestCase):
    def test_pending_and_under_support_add_zero_information(self):
        now = datetime.now(UTC)
        subject = Subject("o/r", "a" * 40)
        trials = tuple(CalibrationTrial("s", str(index), True, True, now) for index in range(2))
        estimate_value = estimate("s", trials)
        pending = CurrentWitness("e1", subject, "c", "s", "PENDING", now)
        passed = CurrentWitness("e2", subject, "c", "s", "PASS", now)
        self.assertEqual(contribution(pending, estimate_value).milli_nats, 0)
        self.assertEqual(contribution(passed, estimate_value).milli_nats, 0)
