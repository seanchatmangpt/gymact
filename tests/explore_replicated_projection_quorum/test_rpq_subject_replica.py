import unittest

from gymact.explore_replicated_projection_quorum.refusal import Refused
from gymact.explore_replicated_projection_quorum.subject import Subject
from tests.explore_replicated_projection_quorum.world import projection


class SubjectReplicaCourt(unittest.TestCase):
    def test_exact_subject_and_replica_identity(self):
        self.assertEqual(Subject("o/r@" + "a" * 40).sha, "a" * 40)
        with self.assertRaisesRegex(Refused, "REFUSED_INEXACT_SUBJECT"):
            Subject("o/r@main")
        self.assertEqual(len(projection("r1").fingerprint), 64)


if __name__ == "__main__":
    unittest.main()
