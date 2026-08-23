import unittest

from gymact.explore_semantic_projection_currentness.currentness import (
    ProjectionEpoch,
    detects_aba,
)
from gymact.explore_semantic_projection_currentness.subject import Subject

from _fixtures import DIGEST, SHA


class Court(unittest.TestCase):
    def test_digest_recurrence_across_generations_is_aba(self):
        subject = Subject("seanchatmangpt/gymact", SHA)
        first = ProjectionEpoch(subject, 1, DIGEST, "b" * 64)
        middle = ProjectionEpoch(subject, 2, DIGEST, "c" * 64)
        returned = ProjectionEpoch(subject, 3, DIGEST, "b" * 64)
        self.assertTrue(detects_aba((first, middle, returned)))


if __name__ == "__main__":
    unittest.main()
