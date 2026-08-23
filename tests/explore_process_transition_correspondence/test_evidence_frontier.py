import unittest

from gymact.explore_process_transition_correspondence.epoch import SubjectEpoch
from gymact.explore_process_transition_correspondence.evidence import Evidence, admit_evidence
from gymact.explore_process_transition_correspondence.frontier import current_frontier
from gymact.explore_process_transition_correspondence.identity import Refused, Subject
from gymact.explore_process_transition_correspondence.obligation import ObligationState


class EvidenceFrontierCourt(unittest.TestCase):
    def test_stale_and_divergent_currentness_refuse(self) -> None:
        a = SubjectEpoch(Subject.parse("o/r@" + "a" * 40), 1)
        b = SubjectEpoch(Subject.parse("o/r@" + "b" * 40), 2)
        with self.assertRaisesRegex(Refused, "STALE_OR_FUTURE"):
            admit_evidence(Evidence(a, "CI", ObligationState.PASS, "run-1"), b)
        self.assertEqual(current_frontier([a, b]), b)
        c = SubjectEpoch(Subject.parse("o/r@" + "c" * 40), 2)
        with self.assertRaisesRegex(Refused, "DIVERGENT_CURRENT_FRONTIER"):
            current_frontier([a, b, c])


if __name__ == "__main__":
    unittest.main()
