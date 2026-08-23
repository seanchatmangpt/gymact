from fractions import Fraction
import unittest

from gymact.explore_projection_sensor_fusion.calibration import Calibration
from gymact.explore_projection_sensor_fusion.independence import IndependenceProof
from gymact.explore_projection_sensor_fusion.refusals import FusionRefused
from gymact.explore_projection_sensor_fusion.sensor import SensorIdentity
from gymact.explore_projection_sensor_fusion.subject import Subject


class IdentityCalibrationCourt(unittest.TestCase):
    def test_exact_subject_and_independence(self) -> None:
        Subject("seanchatmangpt/gymact@" + "a" * 40)
        with self.assertRaises(FusionRefused):
            Subject("seanchatmangpt/gymact@short")
        a = SensorIdentity("a", "family-a", "domain-a", 1, "1" * 64)
        b = SensorIdentity("b", "family-b", "domain-b", 1, "2" * 64)
        calibration = Calibration(a, 20, Fraction(1, 20), Fraction(1, 10), Fraction(1, 20))
        self.assertEqual(calibration.error_mass, Fraction(1, 5))
        self.assertEqual(IndependenceProof(a, b, "3" * 64).pair(), frozenset({"a", "b"}))
        with self.assertRaises(FusionRefused):
            IndependenceProof(a, SensorIdentity("c", "family-a", "domain-c", 1, "4" * 64), "5" * 64)


if __name__ == "__main__":
    unittest.main()
