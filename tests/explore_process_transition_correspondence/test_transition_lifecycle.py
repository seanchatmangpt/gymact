import unittest

from gymact.explore_process_transition_correspondence.discharge import Discharge
from gymact.explore_process_transition_correspondence.epoch import SubjectEpoch
from gymact.explore_process_transition_correspondence.identity import Refused, Subject
from gymact.explore_process_transition_correspondence.obligation import ObligationState
from gymact.explore_process_transition_correspondence.regression import Regression
from gymact.explore_process_transition_correspondence.transition import Transition


class TransitionLifecycleCourt(unittest.TestCase):
    def test_contiguous_discharge_and_regression(self) -> None:
        a = SubjectEpoch(Subject.parse("o/r@" + "a" * 40), 1)
        b = SubjectEpoch(Subject.parse("o/r@" + "b" * 40), 2)
        self.assertEqual(Transition(a, b).after.generation, 2)
        d = Discharge("TLS", ObligationState.FAIL, ObligationState.PASS, "run-2")
        self.assertEqual(d.proof_source_id, "run-2")
        r = Regression("CI", ObligationState.PASS, ObligationState.FAIL)
        self.assertEqual(r.severity, 2)
        with self.assertRaisesRegex(Refused, "NONCONTIGUOUS"):
            Transition(a, SubjectEpoch(b.subject, 3))


if __name__ == "__main__":
    unittest.main()
