import unittest

from gymact.explore_process_trace_correspondence.bisimulation import bounded_bisimulation
from gymact.explore_process_trace_correspondence.event import Event
from gymact.explore_process_trace_correspondence.subject import Subject
from gymact.explore_process_trace_correspondence.trace import Trace


class BisimulationCourt(unittest.TestCase):
    def test_first_divergence_is_preserved(self):
        subject = Subject("owner/repo@" + "c" * 40)
        left = Trace(subject, "BEAM", (Event("A", "o"), Event("B", "o")))
        right = Trace(subject, "PLAN", (Event("A", "o"), Event("C", "o")))
        witness = bounded_bisimulation(left, right, 8)
        self.assertFalse(witness.complete)
        self.assertEqual(witness.matched_steps, 1)
        self.assertEqual(witness.divergence.index, 1)


if __name__ == "__main__":
    unittest.main()
