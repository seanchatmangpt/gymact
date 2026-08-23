import unittest
from datetime import datetime, timezone
from fractions import Fraction

from gymact.explore_rail_consensus.calibration import RailCalibration
from gymact.explore_rail_consensus.clusters import correlated_clusters
from gymact.explore_rail_consensus.consensus import ConsensusStrategy, evaluate
from gymact.explore_rail_consensus.observation import Outcome, RailObservation
from gymact.explore_rail_consensus.rail import VerificationRail
from gymact.explore_rail_consensus.relation import IndependenceProof
from gymact.explore_rail_consensus.subject import Subject

class ConsensusTest(unittest.TestCase):
    def test_calibrated_independent_quorum_and_failure_dominance(self):
        subject = Subject("o/r", "e" * 40)
        now = datetime.now(timezone.utc)
        left_rail = VerificationRail(subject, "a", "pytest", "runtime", "py", "a")
        right_rail = VerificationRail(subject, "b", "world", "sim", "py", "b")
        left = RailObservation(left_rail, "1", Outcome.PASS, now)
        right = RailObservation(right_rail, "2", Outcome.PASS, now)
        proof = IndependenceProof(left_rail.fingerprint, right_rail.fingerprint, "proof")
        calibration = RailCalibration(8, Fraction(0), Fraction(0), Fraction(1))
        calibrations = {left_rail.fingerprint: calibration, right_rail.fingerprint: calibration}
        clusters = correlated_clusters((left, right), (proof,))
        result = evaluate(clusters, calibrations, ConsensusStrategy.QUORUM_CALIBRATED)
        self.assertEqual(result.standing, "PARTIAL_ALIVE")
        failed = RailObservation(right_rail, "3", Outcome.FAIL, now)
        result = evaluate(correlated_clusters((left, failed), (proof,)), calibrations, ConsensusStrategy.QUORUM_CALIBRATED)
        self.assertEqual(result.standing, "BUILD_BROKEN")
