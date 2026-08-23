import unittest

from gymact.explore_process_trace_correspondence.bisimulation import bounded_bisimulation
from gymact.explore_process_trace_correspondence.event import Event
from gymact.explore_process_trace_correspondence.subject import Subject
from gymact.explore_process_trace_correspondence.trace import Trace


class BisimulationCourt(unittest.TestCase):
    def test_first_divergence_is_preserved(self):
        s = Subject("owner/repo@" + "c" * 40)
        a = Trace(s, "BEAM", (Event("A", "o"), Event("B", "o")))
        b = Trace(s, "PLAN", (Event("A", "o"), Event("C", "o")))
        w = bounded_bisimulation(a, b, 8)
        self.assertFalse(w.complete)
        self.assertEqual(w.matched_steps, 1)
        self.assertEqual(w.divergence.index, 1)


if __name__ == "__main__": unittest.main()
