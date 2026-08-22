import unittest

from gymact.explore_evidence_calibration.contracts import Refusal, Subject


class ContractTests(unittest.TestCase):
    def test_exact_subject_only(self):
        subject = Subject("seanchatmangpt/gymact", "a" * 40)
        self.assertEqual(subject.exact_id, "seanchatmangpt/gymact@" + "a" * 40)
        with self.assertRaisesRegex(Refusal, "REFUSED_INEXACT_SUBJECT"):
            Subject("seanchatmangpt/gymact", "a" * 8)
