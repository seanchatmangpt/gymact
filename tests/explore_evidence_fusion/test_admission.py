import unittest
from datetime import UTC, datetime, timedelta

from gymact.explore_evidence_fusion.admission import admit
from gymact.explore_evidence_fusion.observation import Observation
from gymact.explore_evidence_fusion.source import EvidenceSource
from gymact.explore_evidence_fusion.subject import Subject

N = datetime(2026, 8, 22, 18, 0, tzinfo=UTC)


class T(unittest.TestCase):
    def test_future_evidence_refused(self):
        sub = Subject("seanchatmangpt/gymact@" + "a" * 40)
        src = EvidenceSource("seanchatmangpt/gymact", "r1", "1" * 64, "fam")
        with self.assertRaisesRegex(ValueError, "FUTURE"):
            admit([Observation(src, "FOCUSED", "PASS", N + timedelta(seconds=1), "e1")], sub, N)
