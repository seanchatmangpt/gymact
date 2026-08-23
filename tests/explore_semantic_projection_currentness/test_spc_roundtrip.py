import unittest
from fractions import Fraction

from gymact.explore_semantic_projection_currentness.roundtrip import witness
from gymact.explore_semantic_projection_currentness.subject import Refusal

from _fixtures import fixtures


class Court(unittest.TestCase):
    def test_lossy_roundtrip_typed_refuses(self):
        _, rdf, ash, _, graph, _, _ = fixtures(Fraction(1, 10))
        with self.assertRaisesRegex(Refusal, "REFUSED_LOSSY_ROUNDTRIP"):
            witness(graph, rdf, ash, require_lossless=True)


if __name__ == "__main__":
    unittest.main()
