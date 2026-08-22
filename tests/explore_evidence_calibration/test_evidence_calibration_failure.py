import unittest
from datetime import datetime,timezone
from gymact.explore_evidence_calibration.contracts import Subject
from gymact.explore_evidence_calibration.failure import inject_miscalibration
from gymact.explore_evidence_calibration.witness import CurrentWitness
class FailureTests(unittest.TestCase):
    def test_seeded_failure_replays(self):
        now=datetime.now(timezone.utc); subject=Subject("o/r","a"*40)
        witnesses=tuple(CurrentWitness(str(i),subject,"c","s","PASS",now) for i in range(5))
        self.assertEqual(inject_miscalibration(witnesses,seed=7,probability_ppm=500_000),inject_miscalibration(witnesses,seed=7,probability_ppm=500_000))
