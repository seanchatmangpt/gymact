import unittest

from gymact.explore_projection_sensor_fusion.audit import audit_root
from gymact.explore_projection_sensor_fusion.faults import Fault, FaultWorld
from gymact.explore_projection_sensor_fusion.storage import StorageKind, select_storage


class FaultStorageAuditCourt(unittest.TestCase):
    def test_replay_storage_and_order_invariance(self) -> None:
        faults = tuple(Fault)
        self.assertEqual(FaultWorld(42).choose(faults), FaultWorld(42).choose(faults))
        self.assertEqual(select_storage(durable=True, transactional=True).kind, StorageKind.SQLITE)
        left = audit_root(("1" * 64, "2" * 64, "3" * 64))
        right = audit_root(("3" * 64, "1" * 64, "2" * 64))
        self.assertEqual(left, right)


if __name__ == "__main__":
    unittest.main()
