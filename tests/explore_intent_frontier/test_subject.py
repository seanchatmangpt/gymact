import unittest

from gymact.explore_intent_frontier.subject import Subject


class TestSubject(unittest.TestCase):
    def test_exact_identity_and_short_refusal(self):
        s = Subject("seanchatmangpt/gymact", "a" * 40)
        self.assertEqual(s.identity, "seanchatmangpt/gymact@" + "a" * 40)
        with self.assertRaisesRegex(ValueError, "REFUSED_INEXACT_SUBJECT"):
            Subject("gymact", "abc")


if __name__ == "__main__":
    unittest.main()
