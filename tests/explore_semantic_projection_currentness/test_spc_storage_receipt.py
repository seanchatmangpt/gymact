import unittest
from dataclasses import replace

from _fixtures import SHA

from gymact.explore_semantic_projection_currentness.receipt import (
    ProjectionReceipt,
    require_do,
)
from gymact.explore_semantic_projection_currentness.storage import (
    StorageKind,
    select_storage,
)
from gymact.explore_semantic_projection_currentness.subject import Refusal, Subject


class Court(unittest.TestCase):
    def test_transactional_storage_receipt_replay_and_do_refusal(self):
        storage = select_storage(durable=True, transactional=True)
        self.assertEqual(storage.kind, StorageKind.SQLITE)
        receipt = ProjectionReceipt(
            Subject("seanchatmangpt/gymact", SHA),
            "urn:example:type:Temperature",
            "f" * 64,
            "MAX_FIDELITY",
            "e" * 64,
            "SQLITE",
            "PARTIAL_ALIVE",
        )
        self.assertTrue(receipt.replay(receipt.digest))
        changed = replace(receipt, standing="REQUALIFYING")
        self.assertFalse(changed.replay(receipt.digest))
        with self.assertRaisesRegex(Refusal, "REFUSED_UNRECEIPTED_ACTUATION"):
            require_do()


if __name__ == "__main__":
    unittest.main()
