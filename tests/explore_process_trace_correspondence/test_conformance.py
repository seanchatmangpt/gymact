import unittest

from gymact.explore_process_trace_correspondence.conformance import compare
from gymact.explore_process_trace_correspondence.event import Event
from gymact.explore_process_trace_correspondence.subject import Subject
from gymact.explore_process_trace_correspondence.trace import Trace


class ConformanceCourt(unittest.TestCase):
    def test_precision_and_recall_remain_distinct(self):
        s = Subject("owner/repo@" + "d" * 40)
        expected = Trace(s, "MODEL", (Event("A", "o"), Event("B", "o"), Event("C", "o")))
        observed = Trace(s, "BEAM", (Event("A", "o"), Event("B", "o")))
        score = compare(expected, observed)
        self.assertEqual(score.precision, 1.0)
        self.assertAlmostEqual(score.recall, 2 / 3)


if __name__ == "__main__": unittest.main()
