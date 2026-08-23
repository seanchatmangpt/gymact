import unittest
from datetime import UTC, datetime
from fractions import Fraction

from gymact.explore_sequential_acquisition.belief import BeliefState
from gymact.explore_sequential_acquisition.evidence import ObservationEvidence
from gymact.explore_sequential_acquisition.update import update_belief


class BeliefCourt(unittest.TestCase):
    def test_update_and_zero_mass(self):
        prior = BeliefState(("a", "b"), (Fraction(1, 2), Fraction(1, 2)))
        evidence = ObservationEvidence(
            "a" * 64,
            "hit",
            (Fraction(3, 4), Fraction(1, 4)),
            datetime.now(UTC),
        )
        posterior = update_belief(prior, evidence)
        self.assertEqual(posterior.probabilities, (Fraction(3, 4), Fraction(1, 4)))
        zero = ObservationEvidence(
            "a" * 64,
            "none",
            (Fraction(0), Fraction(0)),
            datetime.now(UTC),
        )
        with self.assertRaisesRegex(ValueError, "REFUSED_ZERO_EVIDENCE_MASS"):
            update_belief(prior, zero)


if __name__ == "__main__":
    unittest.main()
