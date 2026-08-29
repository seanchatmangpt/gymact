from dataclasses import dataclass

from .certificate import Certificate
from .refusal import FederationRefusal


@dataclass(frozen=True)
class Federation:
    certificates: tuple[Certificate, ...]

    def __post_init__(self) -> None:
        if not self.certificates:
            raise FederationRefusal("EMPTY_FEDERATION")
        subjects = {c.subject.identity for c in self.certificates}
        if len(subjects) != 1:
            raise FederationRefusal("SUBJECT_DIVERGENCE")
        identities = [c.identity for c in self.certificates]
        if len(set(identities)) != len(identities):
            raise FederationRefusal("DUPLICATE_CERTIFICATE")

    @property
    def subject_identity(self) -> str:
        return self.certificates[0].subject.identity
