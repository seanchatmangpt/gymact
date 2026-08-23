import unittest

from gymact.explore_projection_sensor_fusion.authority import ActionClass, require_authority
from gymact.explore_projection_sensor_fusion.receipt import Receipt
from gymact.explore_projection_sensor_fusion.refusals import FusionRefused
from gymact.explore_projection_sensor_fusion.replay import replay
from gymact.explore_projection_sensor_fusion.subject import Subject


class ReplayAuthorityCourt(unittest.TestCase):
    def test_receipt_replay_and_do_refusal(self) -> None:
        receipt = Receipt(Subject("seanchatmangpt/gymact@" + "a" * 40), "MIN_COST", "s1", "b" * 64, "PARTIAL_ALIVE")
        self.assertEqual(replay(receipt, receipt.digest), "REPLAY_MATCH")
        with self.assertRaises(FusionRefused):
            replay(receipt, "0" * 64)
        with self.assertRaises(FusionRefused):
            require_authority(ActionClass.DO)


if __name__ == "__main__":
    unittest.main()
