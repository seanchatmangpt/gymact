import unittest

from gymact.explore_process_transition_correspondence.epoch import SubjectEpoch
from gymact.explore_process_transition_correspondence.identity import Refused, Subject


class IdentityEpochCourt(unittest.TestCase):
    def test_exact_identity_and_monotone_epoch(self) -> None:
        first = Subject.parse("o/r@" + "a" * 40)
        second = Subject.parse("o/r@" + "b" * 40)
        epoch = SubjectEpoch(first, 3)
        self.assertEqual(epoch.successor(second).generation, 4)
        with self.assertRaisesRegex(Refused, "INEXACT"):
            Subject.parse("o/r@abc")
        with self.assertRaisesRegex(Refused, "NONADVANCING"):
            epoch.successor(first)


if __name__ == "__main__":
    unittest.main()
