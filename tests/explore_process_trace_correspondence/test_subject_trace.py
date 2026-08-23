import unittest

from gymact.explore_process_trace_correspondence.event import Event
from gymact.explore_process_trace_correspondence.refusal import Refused
from gymact.explore_process_trace_correspondence.subject import Subject
from gymact.explore_process_trace_correspondence.trace import Trace


class SubjectTraceCourt(unittest.TestCase):
    def test_exact_subject_and_nonempty_trace(self):
        subject = Subject("owner/repo@" + "a" * 40)
        trace = Trace(subject, "BEAM", (Event("A", "o1"),))
        self.assertEqual(trace.subject, subject)
        with self.assertRaises(Refused):
            Subject("owner/repo@short")
        with self.assertRaises(Refused):
            Trace(subject, "BEAM", ())


if __name__ == "__main__":
    unittest.main()
