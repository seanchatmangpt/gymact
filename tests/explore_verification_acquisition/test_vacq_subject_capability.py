import unittest

from gymact.explore_verification_acquisition.capability import RailCapability
from gymact.explore_verification_acquisition.subject import Refusal, Subject


class SubjectCapabilityTest(unittest.TestCase):
    def test_exact_subject_and_bounded_cost(self):
        subject = Subject("o/r", "a" * 40)
        rail = RailCapability(
            subject,
            "ci",
            "pytest",
            "runtime",
            frozenset({"unit"}),
            10,
            20,
        )
        self.assertEqual(rail.fingerprint, rail.fingerprint)
        with self.assertRaisesRegex(Refusal, "REFUSED_INEXACT_SUBJECT"):
            Subject("o/r", "abc")
        with self.assertRaisesRegex(Refusal, "REFUSED_INVALID_RAIL_COST"):
            RailCapability(
                subject,
                "bad",
                "pytest",
                "runtime",
                frozenset({"unit"}),
                0,
                20,
            )
