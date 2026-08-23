import unittest
from gymact.explore_realized_acquisition_feedback.subject import Refusal, Subject

class TestSubject(unittest.TestCase):
    def test_short_sha_refuses(self):
        with self.assertRaisesRegex(Refusal, "REFUSED_INEXACT_SUBJECT"):
            Subject("seanchatmangpt/gymact", "abc")
