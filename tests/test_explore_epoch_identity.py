import unittest

from gymact.explore_epoch.identity import Subject


class TestEpochIdentity(unittest.TestCase):
    def test_exact_sha_only(self):
        with self.assertRaisesRegex(ValueError, "REFUSED_INEXACT_SUBJECT_SHA"):
            Subject("o/r", "abc")
        self.assertEqual(Subject("o/r", "a" * 40).key, "o/r@" + "a" * 40)


if __name__ == "__main__":
    unittest.main()
