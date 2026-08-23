import unittest
from fractions import Fraction

from gymact.explore_causal_sensitivity import (
    ActionClass,
    Subject,
    admit_action,
    evaluate,
    make_receipt,
)
from gymact.explore_causal_sensitivity.evidence import LoggedOutcome
from gymact.explore_causal_sensitivity.replay import replay


class ChicagoSensitivityTest(unittest.TestCase):
    def test_end_to_end_non_actuating_sensitivity_receipt(self) -> None:
        subject = Subject.parse("seanchatmangpt/gymact@" + "c" * 40)
        rows = (
            LoggedOutcome("ctx-1", "probe-a", Fraction(3, 4), Fraction(1, 2), Fraction(2, 3)),
            LoggedOutcome("ctx-2", "probe-b", Fraction(1, 4), Fraction(1, 2), Fraction(1, 3)),
        )
        result = evaluate(rows, Fraction(3, 2), Fraction(1))
        self.assertEqual(result.standing, "PARTIAL_ALIVE")
        self.assertLessEqual(result.interval.lower, result.interval.upper)
        self.assertIsNotNone(admit_action(ActionClass.DO))
        receipt = make_receipt(subject, "ROBUST_IPS", result.standing)
        self.assertFalse(receipt.actuation_performed)
        self.assertTrue(replay(receipt, receipt.digest()))


if __name__ == "__main__":
    unittest.main()
