import unittest
from datetime import datetime, timezone

from gymact.explore_rail_consensus.observation import Outcome, RailObservation
from gymact.explore_rail_consensus.rail import VerificationRail
from gymact.explore_rail_consensus.relation import EvidenceRelation, IndependenceProof, relation
from gymact.explore_rail_consensus.subject import Subject

class RelationTest(unittest.TestCase):
    def test_explicit_independence_precedes_heuristic_correlation(self):
        subject = Subject("o/r", "c" * 40)
        now = datetime.now(timezone.utc)
        left = RailObservation(VerificationRail(subject, "a", "pytest", "runtime", "py", "x"), "1", Outcome.PASS, now)
        right = RailObservation(VerificationRail(subject, "b", "pytest", "runtime", "py", "y"), "2", Outcome.PASS, now)
        self.assertEqual(relation(left, right), EvidenceRelation.CORRELATED)
        proof = IndependenceProof(left.rail.fingerprint, right.rail.fingerprint, "proof", True)
        self.assertEqual(relation(left, right, (proof,)), EvidenceRelation.INDEPENDENT)
