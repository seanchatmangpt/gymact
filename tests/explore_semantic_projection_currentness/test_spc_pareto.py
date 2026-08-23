import unittest
from fractions import Fraction

from gymact.explore_semantic_projection_currentness.pareto import frontier
from gymact.explore_semantic_projection_currentness.selectors import Score

from _fixtures import fixtures


class Court(unittest.TestCase):
    def test_strictly_dominated_representation_is_removed(self):
        _, rdf, ash, *_ = fixtures()
        dominant = Score(rdf, Fraction(0), 0, 1, 1)
        dominated = Score(ash, Fraction(1, 2), 4, 4, 0)
        self.assertEqual(frontier((dominant, dominated)), (dominant,))


if __name__ == "__main__":
    unittest.main()
