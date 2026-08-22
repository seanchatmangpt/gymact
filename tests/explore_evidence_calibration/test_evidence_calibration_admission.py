import unittest
from datetime import UTC, datetime

from gymact.explore_evidence_calibration.admission import admit
from gymact.explore_evidence_calibration.contracts import Refusal, Subject
from gymact.explore_evidence_calibration.witness import CurrentWitness, EvidenceCluster


class AdmissionTests(unittest.TestCase):
    def test_overlapping_cluster_refuses(self):
        subject = Subject("o/r", "a" * 40)
        now = datetime.now(UTC)
        clusters = (EvidenceCluster("c1", ("s",)), EvidenceCluster("c2", ("s",)))
        witness = CurrentWitness("e", subject, "c1", "s", "PASS", now)
        with self.assertRaisesRegex(Refusal, "OVERLAPPING"):
            admit(subject, clusters, (witness,), (), now=now)
