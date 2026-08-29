import unittest

from gymact.explore_process_transition_correspondence.dependency import propagate_blockers
from gymact.explore_process_transition_correspondence.obligation import ObligationState
from gymact.explore_process_transition_correspondence.standing import Standing, standing


class DependencyStandingCourt(unittest.TestCase):
    def test_red_parent_blocks_and_dominates(self) -> None:
        states = {"semantic": ObligationState.PASS, "runtime": ObligationState.FAIL}
        blocked = propagate_blockers({"replay": {"runtime"}}, states)
        self.assertEqual(blocked, {"replay"})
        self.assertEqual(standing(list(states.values()), blocked=bool(blocked)), Standing.BUILD_BROKEN)
        self.assertEqual(standing([ObligationState.PASS]), Standing.PARTIAL_ALIVE)


if __name__ == "__main__":
    unittest.main()
