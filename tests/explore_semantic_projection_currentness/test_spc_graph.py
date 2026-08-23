import unittest

from tests.explore_semantic_projection_currentness._fixtures import fixtures


class Court(unittest.TestCase):
    def test_shortest_path_preserves_conversion_topology(self):
        _, rdf, _, wasm, graph, _, _ = fixtures()
        path = graph.shortest(rdf, wasm)
        self.assertEqual([edge.name for edge in path.converters], ["rdf_to_wasm"])
        self.assertEqual(path.cost, 2)


if __name__ == "__main__":
    unittest.main()
