import unittest

from gymact.explore_causal_sensitivity import ActionClass, Subject, admit_action


class IdentityAuthorityTest(unittest.TestCase):
    def test_subject_requires_exact_sha(self) -> None:
        with self.assertRaises(ValueError):
            Subject.parse("owner/repo@main")
        subject = Subject.parse("owner/repo@" + "a" * 40)
        self.assertEqual(subject.canonical(), "owner/repo@" + "a" * 40)

    def test_direct_do_is_refused(self) -> None:
        refusal = admit_action(ActionClass.DO)
        self.assertIsNotNone(refusal)
        self.assertEqual(refusal.code.value, "REFUSED_UNRECEIPTED_ACTUATION")
        self.assertIsNone(admit_action(ActionClass.SELECT))


if __name__ == "__main__":
    unittest.main()
