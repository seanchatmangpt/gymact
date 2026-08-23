import unittest

from gymact.explore_robustness_bound_calibration import Refused, Subject


class SubjectCourt(unittest.TestCase):
    def test_exact_subject_only(self) -> None:
        subject = Subject("seanchatmangpt/gymact@" + "a" * 40)
        self.assertEqual(subject.sha, "a" * 40)
        with self.assertRaises(Refused):
            Subject("seanchatmangpt/gymact@abc")


if __name__ == "__main__":
    unittest.main()
