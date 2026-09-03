import unittest
from datetime import UTC, datetime

from gymact.explore_rail_consensus.clusters import correlated_clusters
from gymact.explore_rail_consensus.observation import Outcome, RailObservation
from gymact.explore_rail_consensus.rail import VerificationRail
from gymact.explore_rail_consensus.subject import Subject


class ClusterTest(unittest.TestCase):
    def test_same_family_collapses(self):
        subject = Subject("o/r", "d" * 40)
        now = datetime.now(UTC)
        observations = tuple(
            RailObservation(
                VerificationRail(subject, str(i), "pytest", "runtime", "py", str(i)),
                str(i),
                Outcome.PASS,
                now,
            )
            for i in range(3)
        )
        self.assertEqual(len(correlated_clusters(observations)), 1)
