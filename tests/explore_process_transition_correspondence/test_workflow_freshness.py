import unittest
from datetime import datetime, timedelta, timezone

from gymact.explore_process_transition_correspondence.freshness import TimedEvidence, require_fresh
from gymact.explore_process_transition_correspondence.identity import Refused, Subject
from gymact.explore_process_transition_correspondence.obligation import ObligationState
from gymact.explore_process_transition_correspondence.workflow import WorkflowConclusion, WorkflowEvidence, workflow_state


class WorkflowFreshnessCourt(unittest.TestCase):
    def test_head_and_time_are_independent_admission_axes(self) -> None:
        current = Subject.parse("o/r@" + "a" * 40)
        foreign = Subject.parse("o/r@" + "b" * 40)
        with self.assertRaisesRegex(Refused, "FOREIGN_WORKFLOW_HEAD"):
            workflow_state(WorkflowEvidence(foreign, WorkflowConclusion.SUCCESS), current)
        self.assertEqual(workflow_state(WorkflowEvidence(current, WorkflowConclusion.PENDING), current), ObligationState.UNKNOWN)
        now = datetime(2026, 8, 23, 8, 20, tzinfo=timezone.utc)
        with self.assertRaisesRegex(Refused, "STALE_EVIDENCE"):
            require_fresh(TimedEvidence(now - timedelta(hours=3)), now=now, ttl=timedelta(hours=2))


if __name__ == "__main__":
    unittest.main()
