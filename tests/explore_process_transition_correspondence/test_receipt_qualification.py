import unittest

from gymact.explore_process_transition_correspondence.authority import ActionClass, admit_action
from gymact.explore_process_transition_correspondence.identity import Refused, Subject
from gymact.explore_process_transition_correspondence.obligation import Obligation, ObligationState
from gymact.explore_process_transition_correspondence.qualification import qualify
from gymact.explore_process_transition_correspondence.replay import replay
from gymact.explore_process_transition_correspondence.standing import Standing


class ReceiptQualificationCourt(unittest.TestCase):
    def test_partial_alive_replays_without_actuation(self) -> None:
        subject = Subject.parse("o/r@" + "a" * 40)
        q = qualify(subject, [Obligation("semantic", ObligationState.PASS, "run-1"), Obligation("runtime", ObligationState.PASS, "run-2")])
        self.assertEqual(q.standing, Standing.PARTIAL_ALIVE)
        self.assertTrue(replay(q.receipt, q.receipt.digest()))
        with self.assertRaisesRegex(Refused, "UNRECEIPTED_ACTUATION"):
            admit_action(ActionClass.DO)
        with self.assertRaisesRegex(Refused, "RECEIPT_TAMPER"):
            replay(q.receipt, "0" * 64)


if __name__ == "__main__":
    unittest.main()
