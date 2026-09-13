import unittest

from gymact.explore_epoch.identity import Subject
from gymact.explore_epoch.topology import DependencyGraph


class TestEpochTopology(unittest.TestCase):
    def test_cycle_refused(self):
        a = Subject("o/a", "a" * 40)
        b = Subject("o/b", "b" * 40)
        with self.assertRaisesRegex(ValueError, "REFUSED_DEPENDENCY_CYCLE"):
            DependencyGraph(((a, b), (b, a))).consumers(a)


if __name__ == "__main__":
    unittest.main()
