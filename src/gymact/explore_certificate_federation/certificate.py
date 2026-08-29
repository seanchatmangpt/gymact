from dataclasses import dataclass
import hashlib

from .refusal import FederationRefusal
from .subject import Subject


@dataclass(frozen=True)
class Certificate:
    subject: Subject
    engine_id: str
    semantic_digest: str
    result_digest: str
    generation: int

    def __post_init__(self) -> None:
        if not self.engine_id.strip() or self.generation < 0:
            raise FederationRefusal("INVALID_CERTIFICATE")
        for digest in (self.semantic_digest, self.result_digest):
            if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
                raise FederationRefusal("INVALID_DIGEST")

    @property
    def identity(self) -> str:
        body = f"{self.subject.identity}|{self.engine_id}|{self.semantic_digest}|{self.result_digest}|{self.generation}"
        return hashlib.sha256(body.encode()).hexdigest()
