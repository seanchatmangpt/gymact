import unittest
from gymact.explore_invalidation.model import Refusal, Subject

class T(unittest.TestCase):
    def test_exact_subject(self):
        self.assertTrue(Subject("o/r", "a"*40).identity.endswith("a"*40))
        with self.assertRaisesRegex(Refusal, "REFUSED_INEXACT_SUBJECT"):
            Subject("o/r", "abc")
