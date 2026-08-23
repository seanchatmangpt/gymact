import unittest

from _fixtures import fixtures

from gymact.explore_semantic_projection_currentness.representation import RepresentationKind
from gymact.explore_semantic_projection_currentness.selectors import (
    SelectorKind,
    score,
    select,
)


class Court(unittest.TestCase):
    def test_distinct_selectors_remain_executable(self):
        _, rdf, ash, wasm, _, ash_witness, wasm_witness = fixtures()
        scores = (
            score(rdf, None),
            score(ash, ash_witness),
            score(wasm, wasm_witness),
        )
        cheap = select(SelectorKind.MIN_MIGRATION_COST, scores)
        reversible = select(SelectorKind.MAX_REVERSIBILITY, scores)
        self.assertEqual(cheap.candidate.kind, RepresentationKind.RDF_TERM)
        self.assertTrue(reversible.candidate.reversible)
        self.assertEqual(len(SelectorKind), 4)


if __name__ == "__main__":
    unittest.main()
