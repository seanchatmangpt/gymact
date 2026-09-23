import unittest
from datetime import UTC, datetime

from gymact.explore_evidence_fusion.observation import Observation
from gymact.explore_evidence_fusion.source import EvidenceSource


class T(unittest.TestCase):
    def test_observation_time_and_vocab(self):
        s = EvidenceSource("seanchatmangpt/gymact", "r1", "1" * 64, "fam")
        o = Observation(s, "FOCUSED", "PASS", datetime.now(UTC), "e1")
        self.assertEqual(o.outcome, "PASS")
        with self.assertRaisesRegex(ValueError, "NAIVE"):
            Observation(s, "FOCUSED", "PASS", datetime(2026, 1, 1), "e2")
