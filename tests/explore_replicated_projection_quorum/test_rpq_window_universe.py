import unittest
from fractions import Fraction

from .world import NOW, UNIVERSE, WINDOW


class WindowUniverseCourt(unittest.TestCase):
    def test_half_open_window_and_exact_coverage(self):
        self.assertTrue(WINDOW.contains(NOW))
        self.assertFalse(WINDOW.contains(WINDOW.until))
        self.assertEqual(UNIVERSE.quorum_size, 3)
        self.assertEqual(UNIVERSE.coverage({"r1", "r2"}), Fraction(2, 5))


if __name__ == "__main__":
    unittest.main()
