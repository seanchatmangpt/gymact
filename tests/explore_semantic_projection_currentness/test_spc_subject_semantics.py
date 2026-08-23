import unittest

from _fixtures import DIGEST, SHA

from gymact.explore_semantic_projection_currentness.semantic_type import SemanticType, TermKind
from gymact.explore_semantic_projection_currentness.subject import Refusal, Subject


class Court(unittest.TestCase):
    def test_exact_subject_and_semantic_identity(self):
        subject = Subject("seanchatmangpt/gymact", SHA)
        self.assertEqual(subject.identity, f"seanchatmangpt/gymact@{SHA}")
        with self.assertRaisesRegex(Refusal, "REFUSED_INEXACT_SUBJECT"):
            Subject("seanchatmangpt/gymact", "deadbeef")
        with self.assertRaisesRegex(Refusal, "REFUSED_INVALID_SEMANTIC_IRI"):
            SemanticType("not an iri", TermKind.LITERAL, DIGEST)


if __name__ == "__main__":
    unittest.main()
