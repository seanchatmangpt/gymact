from fractions import Fraction
import unittest

from gymact.explore_projection_sensor_fusion.calibration import Calibration
from gymact.explore_projection_sensor_fusion.distribution import ErrorDistribution
from gymact.explore_projection_sensor_fusion.divergence import jensen_shannon
from gymact.explore_projection_sensor_fusion.fusion import robust_median
from gymact.explore_projection_sensor_fusion.influence import leave_one_out_influence
from gymact.explore_projection_sensor_fusion.sensor import SensorIdentity


def sensor(name: str, digit: str) -> SensorIdentity:
    return SensorIdentity(name, f"family-{name}", f"domain-{name}", 1, digit * 64)


class FusionDifferentialCourt(unittest.TestCase):
    def test_robust_fusion_and_information_geometry(self) -> None:
        rows = (
            Calibration(sensor("a", "1"), 20, Fraction(1, 10), Fraction(1, 10), Fraction(1, 10)),
            Calibration(sensor("b", "2"), 20, Fraction(1, 10), Fraction(1, 5), Fraction(1, 10)),
            Calibration(sensor("c", "3"), 20, Fraction(4, 5), Fraction(1, 10), Fraction(1, 10)),
        )
        fused = robust_median(rows)
        self.assertEqual(fused.false_current, Fraction(1, 10))
        self.assertGreater(leave_one_out_influence(rows)["c"], Fraction(0, 1))
        same = ErrorDistribution(Fraction(1, 2), Fraction(1, 4), Fraction(1, 4))
        other = ErrorDistribution(Fraction(1, 4), Fraction(1, 2), Fraction(1, 4))
        self.assertEqual(jensen_shannon(same, same), 0.0)
        self.assertGreater(jensen_shannon(same, other), 0.0)


if __name__ == "__main__":
    unittest.main()
