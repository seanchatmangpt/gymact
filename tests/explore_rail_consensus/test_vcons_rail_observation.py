import unittest
from datetime import datetime, timezone

from gymact.explore_rail_consensus.observation import Outcome, RailObservation
from gymact.explore_rail_consensus.rail import VerificationRail
from gymact.explore_rail_consensus.subject import Refusal, Subject

class RailObservationTest(unittest.TestCase):
    def test_fingerprint_and_timezone(self):
        subject = Subject("o/r", "b" * 40)
        rail = VerificationRail(subject, "ci", "pytest", "runtime", "py312", "cfg")
        self.assertEqual(rail.fingerprint, rail.fingerprint)
        RailObservation(rail, "1", Outcome.PASS, datetime.now(timezone.utc))
        with self.assertRaisesRegex(Refusal, "REFUSED_NAIVE"):
            RailObservation(rail, "2", Outcome.PASS, datetime.now())
