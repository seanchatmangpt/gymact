import unittest
from fractions import Fraction

from gymact.explore_verification_acquisition.budget import AcquisitionBudget
from gymact.explore_verification_acquisition.calibration import RailCalibration
from gymact.explore_verification_acquisition.capability import RailCapability
from gymact.explore_verification_acquisition.dependence import IndependenceProof
from gymact.explore_verification_acquisition.engine import plan
from gymact.explore_verification_acquisition.storage import PersistenceNeed, Store
from gymact.explore_verification_acquisition.strategies import AcquisitionStrategy
from gymact.explore_verification_acquisition.subject import Subject


class EngineTest(unittest.TestCase):
    def test_constructs_bounded_non_actuating_plan(self):
        subject = Subject("o/r", "4" * 40)
        left = RailCapability(subject, "a", "fa", "da", frozenset({"unit"}), 5, 5)
        right = RailCapability(subject, "b", "fb", "db", frozenset({"e2e"}), 5, 5)
        left_calibration = RailCalibration(left, 10, Fraction(9, 10), Fraction(1, 10))
        right_calibration = RailCalibration(right, 10, Fraction(8, 10), Fraction(1, 10))
        proof = IndependenceProof(left.fingerprint, right.fingerprint, "proof")
        result = plan(
            subject,
            (left, right),
            (left_calibration, right_calibration),
            AcquisitionStrategy.MAX_INFORMATION,
            AcquisitionBudget(10, 10, 2),
            frozenset({"unit", "e2e"}),
            (proof,),
            PersistenceNeed(transactional=True),
        )
        self.assertEqual(result.receipt.standing, "REQUALIFYING")
        self.assertEqual(result.store, Store.SQLITE)
        self.assertFalse(result.receipt.actuation_performed)
