import unittest
from fractions import Fraction

from gymact.explore_verification_acquisition.budget import AcquisitionBudget
from gymact.explore_verification_acquisition.calibration import RailCalibration
from gymact.explore_verification_acquisition.capability import RailCapability
from gymact.explore_verification_acquisition.dependence import IndependenceProof
from gymact.explore_verification_acquisition.engine import plan
from gymact.explore_verification_acquisition.receipt import replay
from gymact.explore_verification_acquisition.strategies import AcquisitionStrategy
from gymact.explore_verification_acquisition.subject import Subject


class E2ETest(unittest.TestCase):
    def test_red_static_rail_drives_bounded_independent_evidence_plan(self):
        subject = Subject("seanchatmangpt/gymact", "5" * 40)
        static = RailCapability(
            subject,
            "ruff",
            "ruff",
            "static",
            frozenset({"style"}),
            2,
            2,
        )
        runtime = RailCapability(
            subject,
            "pytest",
            "pytest",
            "runtime",
            frozenset({"behavior"}),
            10,
            10,
        )
        world = RailCapability(
            subject,
            "world",
            "world-crown",
            "simulation",
            frozenset({"e2e"}),
            15,
            15,
        )
        calibrations = tuple(
            RailCalibration(rail, 12, Fraction(9, 10), Fraction(1, 20))
            for rail in (static, runtime, world)
        )
        proofs = (
            IndependenceProof(static.fingerprint, runtime.fingerprint, "sr"),
            IndependenceProof(static.fingerprint, world.fingerprint, "sw"),
            IndependenceProof(runtime.fingerprint, world.fingerprint, "rw"),
        )
        result = plan(
            subject,
            (static, runtime, world),
            calibrations,
            AcquisitionStrategy.INFORMATION_PER_COST,
            AcquisitionBudget(12, 12, 2),
            frozenset({"style", "behavior", "e2e"}),
            proofs,
        )
        self.assertTrue(result.selection.rails)
        self.assertLessEqual(sum(rail.cost_millis for rail in result.selection.rails), 12)
        self.assertEqual(result.receipt.standing, "REQUALIFYING")
        self.assertTrue(replay(result.receipt, result.receipt.digest))
        self.assertFalse(result.receipt.actuation_performed)
