import hashlib
import pytest

from gymact.explore_certificate_federation.certificate import Certificate
from gymact.explore_certificate_federation.federation import Federation
from gymact.explore_certificate_federation.refusal import FederationRefusal
from gymact.explore_certificate_federation.subject import Subject


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def test_exact_subject_and_certificate_identity() -> None:
    subject = Subject("seanchatmangpt/gymact", "a" * 40, "process")
    cert = Certificate(subject, "solver-a", digest("semantic"), digest("result"), 1)
    assert len(cert.identity) == 64
    assert Federation((cert,)).subject_identity == subject.identity
    with pytest.raises(FederationRefusal, match="INVALID_SUBJECT"):
        Subject("seanchatmangpt/gymact", "short", "process")
