import unittest
from datetime import UTC, datetime
from fractions import Fraction

from gymact.explore_evidence_fusion.observation import Observation
from gymact.explore_evidence_fusion.source import EvidenceSource
from gymact.explore_evidence_fusion.strategies import Strategy, evaluate

N = datetime.now(UTC)


def o(i, out):
    return Observation(
        EvidenceSource("seanchatmangpt/gymact", f"r{i}", str(i) * 64, f"f{i}"),
        "FOCUSED",
        out,
        N,
        f"e{i}",
    )


class T(unittest.TestCase):
    def test_failure_dominates_all_fusion(self):
        d = evaluate(Strategy.CLUSTER_MAJORITY, ((o(1, "PASS"),), (o(2, "FAIL"),)), Fraction(2, 1))
        self.assertEqual(d.standing, "BUILD_BROKEN")
