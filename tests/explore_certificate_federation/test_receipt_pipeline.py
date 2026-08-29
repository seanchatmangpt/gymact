from fractions import Fraction
import hashlib
import pytest

from gymact.explore_certificate_federation.certificate import Certificate
from gymact.explore_certificate_federation.correspondence import RuntimeWitness
from gymact.explore_certificate_federation.independence import ValidatorIdentity
from gymact.explore_certificate_federation.pipeline import verify_federation
from gymact.explore_certificate_federation.receipt import replay
from gymact.explore_certificate_federation.refusal import FederationRefusal
from gymact.explore_certificate_federation.runtime import RuntimeKind, RuntimeProjection
from gymact.explore_certificate_federation.subject import Subject


def d(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def test_pipeline_replay_and_result_divergence() -> None:
    subject = Subject("seanchatmangpt/gymact", "c" * 40, "certificate-federation")
    left = Certificate(subject, "engine-a", d("semantic"), d("result"), 3)
    right = Certificate(subject, "engine-b", d("semantic"), d("result"), 3)
    pair = (
        RuntimeWitness(left, RuntimeProjection(RuntimeKind.BEAM, "impl-a", "env-a")),
        RuntimeWitness(right, RuntimeProjection(RuntimeKind.WASM, "impl-b", "env-b")),
    )
    validators = (
        ValidatorIdentity("validator-a", "model-a", "root-a"),
        ValidatorIdentity("validator-b", "model-b", "root-b"),
    )
    result = verify_federation((left, right), pair, validators, Fraction(0), Fraction(2))
    assert replay(result.receipt, result.receipt.digest)
    assert not result.receipt.actuation_performed
    divergent = Certificate(subject, "engine-c", d("semantic"), d("other"), 3)
    with pytest.raises(FederationRefusal, match="RESULT_DIVERGENCE"):
        verify_federation(
            (left, divergent),
            (pair[0], RuntimeWitness(divergent, pair[1].runtime)),
            validators,
            Fraction(0),
            Fraction(2),
        )
