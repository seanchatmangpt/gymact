import unittest
from fractions import Fraction

from gymact.explore_projection_sensor_fusion.acquisition import AcquisitionCandidate
from gymact.explore_projection_sensor_fusion.authority import ActionClass
from gymact.explore_projection_sensor_fusion.budget import Budget
from gymact.explore_projection_sensor_fusion.calibration import Calibration
from gymact.explore_projection_sensor_fusion.engine import qualify
from gymact.explore_projection_sensor_fusion.independence import IndependenceProof
from gymact.explore_projection_sensor_fusion.replay import replay
from gymact.explore_projection_sensor_fusion.selectors import Selector
from gymact.explore_projection_sensor_fusion.sensor import SensorIdentity
from gymact.explore_projection_sensor_fusion.subject import Subject
from gymact.explore_projection_sensor_fusion.topology import FusionTopology


class ChicagoCourt(unittest.TestCase):
    def test_independent_current_sensors_choose_reversible_acquisition_only(self) -> None:
        a = SensorIdentity("a", "clock", "causal", 2, "1" * 64)
        b = SensorIdentity("b", "receipt", "semantic", 2, "2" * 64)
        calibrations = (
            Calibration(a, 40, Fraction(1, 20), Fraction(1, 20), Fraction(1, 20)),
            Calibration(b, 40, Fraction(1, 10), Fraction(1, 20), Fraction(1, 20)),
        )
        proofs = (IndependenceProof(a, b, "3" * 64),)
        candidates = (
            AcquisitionCandidate(
                "a", Fraction(3, 5), Fraction(1, 5), Fraction(1, 10), 15
            ),
            AcquisitionCandidate(
                "b", Fraction(4, 5), Fraction(4, 5), Fraction(1, 2), 30
            ),
        )
        result = qualify(
            Subject("seanchatmangpt/gymact@" + "a" * 40),
            calibrations,
            proofs,
            candidates,
            Selector.MAX_INDEPENDENCE_GAIN,
            Budget(Fraction(1, 1), 100),
            ActionClass.CONSTRUCT,
        )
        self.assertEqual(result.topology, FusionTopology.HEALTHY)
        self.assertEqual(result.selected.sensor_id, "b")
        self.assertEqual(result.receipt.standing, "PARTIAL_ALIVE")
        self.assertFalse(result.receipt.actuation_performed)
        self.assertEqual(replay(result.receipt, result.receipt.digest), "REPLAY_MATCH")


if __name__ == "__main__":
    unittest.main()
