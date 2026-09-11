import unittest

from tests.explore_semantic_projection_currentness._fixtures import DIGEST, SHA

from gymact.explore_semantic_projection_currentness.currentness import ProjectionEpoch, Transition
from gymact.explore_semantic_projection_currentness.subject import Refusal, Subject


class Court(unittest.TestCase):
    def test_cas_rejects_stale_epoch(self):
        subject = Subject("seanchatmangpt/gymact", SHA)
        before = ProjectionEpoch(subject, 1, DIGEST, "b" * 64)
        after = ProjectionEpoch(subject, 2, DIGEST, "c" * 64)
        stale = ProjectionEpoch(subject, 1, DIGEST, "d" * 64)
        transition = Transition(before.token, before, after)
        self.assertEqual(transition.admit(before), after)
        with self.assertRaisesRegex(Refusal, "REFUSED_STALE_PROJECTION_CAS"):
            transition.admit(stale)


if __name__ == "__main__":
    unittest.main()
