from dataclasses import dataclass
import hashlib

from .refusal import FederationRefusal
from .subject import Subject


@dataclass(frozen=True)
class ReactorIntent:
    subject: Subject
    operation: str
    inputs: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.operation.strip() or any(not value.strip() for value in self.inputs):
            raise FederationRefusal("INVALID_REACTOR_INTENT")

    @property
    def plan_digest(self) -> str:
        body = "|".join((self.subject.identity, self.operation, *self.inputs))
        return hashlib.sha256(body.encode()).hexdigest()

    @property
    def authority(self) -> str:
        return "CONSTRUCT"
