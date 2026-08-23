import pytest

from gymact.explore_decision_realization import Decision, DecisionIdentity, RealizedOutcome, Refused, Subject, admit_outcomes


def subject() -> Subject:
    return Subject.parse("seanchatmangpt/gymact", "a" * 40, "b" * 64)


def decision() -> DecisionIdentity:
    return DecisionIdentity(subject(), "d-1", "risk", 1, "c" * 64, Decision.INDEPENDENT, 10, 0.2)


def test_exact_identity_and_outcome_admission() -> None:
    d = decision()
    out = RealizedOutcome(d.subject, d.decision_id, "o-1", 11, True, 0.0)
    assert admit_outcomes(d, [out]) == (out,)
    with pytest.raises(Refused, match="PREDECISION_OUTCOME"):
        admit_outcomes(d, [RealizedOutcome(d.subject, d.decision_id, "o-2", 10, True, 0.0)])
    with pytest.raises(Refused, match="DUPLICATE_OUTCOME"):
        admit_outcomes(d, [out, out])
