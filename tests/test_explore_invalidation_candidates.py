import unittest
from gymact.explore_invalidation.candidates import discover_candidates
from gymact.explore_invalidation.selection import select_candidate

class T(unittest.TestCase):
    def test_alternatives_preserved(self):
        self.assertEqual({c.name for c in discover_candidates()},{"memory","jsonl","sqlite"})
        self.assertEqual(select_candidate(require_transactional=True).name,"sqlite")
