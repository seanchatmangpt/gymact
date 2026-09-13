import unittest
from datetime import UTC, datetime
from fractions import Fraction

from gymact.explore_rail_consensus.calibration import RailCalibration
from gymact.explore_rail_consensus.consensus import ConsensusStrategy
from gymact.explore_rail_consensus.engine import qualify
from gymact.explore_rail_consensus.observation import Outcome, RailObservation
from gymact.explore_rail_consensus.rail import VerificationRail
from gymact.explore_rail_consensus.receipt import replay
from gymact.explore_rail_consensus.relation import IndependenceProof
from gymact.explore_rail_consensus.storage import PersistenceNeed, Store
from gymact.explore_rail_consensus.subject import Subject


class E2ETest(unittest.TestCase):
    def test_mixed_verification_rails_preserve_failure_topology(self):
        subject = Subject("seanchatmangpt/gymact", "2" * 40)
        now = datetime.now(UTC)
        ci = VerificationRail(subject, "ci", "pytest", "runtime", "py312", "cfg-ci")
        world = VerificationRail(
            subject, "world", "world-crown", "simulation", "py312", "cfg-world"
        )
        proof = IndependenceProof(ci.fingerprint, world.fingerprint, "direct-separate-run-proof")
        calibration = RailCalibration(10, Fraction(0), Fraction(0), Fraction(1))
        calibrations = {ci.fingerprint: calibration, world.fingerprint: calibration}
        green = qualify(
            subject,
            (
                RailObservation(ci, "1", Outcome.PASS, now),
                RailObservation(world, "2", Outcome.PASS, now),
            ),
            calibrations,
            ConsensusStrategy.QUORUM_CALIBRATED,
            (proof,),
            PersistenceNeed(transactional=True),
        )
        self.assertEqual(green.result.standing, "PARTIAL_ALIVE")
        self.assertEqual(green.store, Store.SQLITE)
        self.assertTrue(replay(green.receipt, green.receipt.digest))
        red = qualify(
            subject,
            (
                RailObservation(ci, "3", Outcome.FAIL, now),
                RailObservation(world, "2", Outcome.PASS, now),
            ),
            calibrations,
            ConsensusStrategy.QUORUM_CALIBRATED,
            (proof,),
        )
        self.assertEqual(red.result.standing, "BUILD_BROKEN")
