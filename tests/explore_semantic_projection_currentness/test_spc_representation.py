import unittest

from tests.explore_semantic_projection_currentness._fixtures import fixtures

from gymact.explore_semantic_projection_currentness.representation import (
    RepresentationCandidate,
    RepresentationKind,
)


class Court(unittest.TestCase):
    def test_fingerprints_bind_runtime_representation(self):
        semantic_type, rdf, ash, *_ = fixtures()
        changed = RepresentationCandidate(
            semantic_type,
            RepresentationKind.ASH_PROJECTION,
            (("value", "decimal"), ("unit", "iri")),
            True,
            2,
            1,
        )
        self.assertNotEqual(ash.fingerprint, changed.fingerprint)
        self.assertNotEqual(rdf.fingerprint, ash.fingerprint)


if __name__ == "__main__":
    unittest.main()
