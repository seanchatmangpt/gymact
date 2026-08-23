import pytest

from gymact.explore_validation_independence import (
    Provenance,
    Refused,
    Subject,
    ValidatorWitness,
)


def test_exact_subject_and_validator_alias_refusal():
    subject = Subject.parse("seanchatmangpt/gymact@" + "a" * 40 + "#" + "b" * 64)
    assert subject.repo == "seanchatmangpt/gymact"
    a = ValidatorWitness(
        "a", Provenance("impl-a", "model-a", "domain-a"), "oracle-a"
    )
    b = ValidatorWitness(
        "b", Provenance("impl-b", "model-b", "domain-b"), "oracle-b"
    )
    a.require_independent(b)
    with pytest.raises(Refused, match="UNPROVEN_VALIDATOR_INDEPENDENCE"):
        a.require_independent(
            ValidatorWitness(
                "c", Provenance("impl-a", "model-c", "domain-c"), "oracle-c"
            )
        )
