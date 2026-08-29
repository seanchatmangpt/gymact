from dataclasses import replace
from fractions import Fraction

import pytest

from gymact.explore_kantorovich_independent.authority import admit_authority
from gymact.explore_kantorovich_independent.identity import VerificationSubject
from gymact.explore_kantorovich_independent.receipt import issue_receipt, replay
from gymact.explore_kantorovich_independent.refusal import IndependentVerifierRefusal
from gymact.explore_kantorovich_independent.witness import IndependentWitness


def test_verification_receipt_replays_without_importing_do_authority() -> None:
    subject = VerificationSubject.admit("seanchatmangpt/gymact", "5" * 40, "kantorovich-duality/v1")
    witness = IndependentWitness("gymact.kantorovich.independent-equation-verifier/v1", Fraction(1), Fraction(1), Fraction(0), Fraction(8), 2)
    assert admit_authority("VERIFY").allowed
    receipt = issue_receipt(subject, witness)
    assert replay(receipt)
    assert receipt.actuation_performed is False
    with pytest.raises(IndependentVerifierRefusal, match="UNBROKERED_DO"):
        admit_authority("DO")
    assert admit_authority("DO", "BRCE").allowed
    with pytest.raises(IndependentVerifierRefusal, match="RECEIPT_DIGEST_MISMATCH"):
        replay(replace(receipt, primal="2"))
