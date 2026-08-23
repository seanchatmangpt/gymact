import unittest
from fractions import Fraction

from gymact.explore_semantic_projection_currentness.admission import admit_candidates
from tests.explore_semantic_projection_currentness._fixtures import fixtures


class Court(unittest.TestCase):
    def test_lossless_requirement_preserves_refusal_topology(self):
        semantic_type, rdf, ash, wasm, _, ash_witness, wasm_witness = fixtures(Fraction(1, 10))
        result = admit_candidates(
            semantic_type,
            (rdf, ash, wasm),
            (ash_witness, wasm_witness),
            require_lossless=True,
        )
        self.assertIn(rdf, result.admitted)
        self.assertIn(wasm, result.admitted)
        self.assertIn(
            (ash.fingerprint, "REFUSED_LOSSY_ROUNDTRIP"),
            result.refused,
        )


if __name__ == "__main__":
    unittest.main()
