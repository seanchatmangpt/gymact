import unittest

from gymact.explore_process_trace_correspondence.equivalence import Equivalence, equivalent
from gymact.explore_process_trace_correspondence.event import Event
from gymact.explore_process_trace_correspondence.subject import Subject
from gymact.explore_process_trace_correspondence.trace import Trace


class EquivalenceCourt(unittest.TestCase):
    def test_exact_activity_and_stutter_are_observably_distinct(self):
        subject = Subject("owner/repo@" + "b" * 40)
        left = Trace(subject, "BEAM", (Event("A", "o"), Event("A", "o"), Event("B", "o")))
        right = Trace(subject, "WASM", (Event("A", "o"), Event("B", "o")))
        self.assertFalse(equivalent(left, right, Equivalence.EXACT))
        self.assertFalse(equivalent(left, right, Equivalence.ACTIVITY))
        self.assertTrue(equivalent(left, right, Equivalence.STUTTER))


if __name__ == "__main__": unittest.main()
