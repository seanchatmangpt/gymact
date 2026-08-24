import hashlib
import pytest

from gymact.explore_certificate_federation.certificate import Certificate
from gymact.explore_certificate_federation.correspondence import RuntimeWitness, admit_correspondence
from gymact.explore_certificate_federation.currentness import current_frontier
from gymact.explore_certificate_federation.refusal import FederationRefusal
from gymact.explore_certificate_federation.runtime import RuntimeKind, RuntimeProjection
from gymact.explore_certificate_federation.subject import Subject


def d(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def test_currentness_and_cross_runtime_correspondence() -> None:
    subject = Subject("seanchatmangpt/gymact", "b" * 40, "federated")
    beam = Certificate(subject, "a", d("s"), d("r"), 2)
    wasm = Certificate(subject, "b", d("s"), d("r"), 2)
    assert len(current_frontier((beam, wasm))) == 2
    admit_correspondence(
        RuntimeWitness(beam, RuntimeProjection(RuntimeKind.BEAM, "impl-a", "env-a")),
        RuntimeWitness(wasm, RuntimeProjection(RuntimeKind.WASM, "impl-b", "env-b")),
    )
    divergent = Certificate(subject, "c", d("other"), d("r"), 2)
    with pytest.raises(FederationRefusal, match="DIVERGENT_CURRENT_SEMANTICS"):
        current_frontier((beam, divergent))
