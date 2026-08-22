import unittest

from gymact.explore_evidence_calibration.storage import StoreKind, candidates, select


class StorageTests(unittest.TestCase):
    def test_reversible_candidates_and_transactional_selection(self):
        self.assertEqual(
            {candidate.kind for candidate in candidates()},
            {StoreKind.MEMORY, StoreKind.JSONL, StoreKind.SQLITE},
        )
        self.assertEqual(select(durable=True, transactional=True).kind, StoreKind.SQLITE)
