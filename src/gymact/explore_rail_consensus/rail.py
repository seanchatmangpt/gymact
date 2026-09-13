import hashlib
import json
from dataclasses import dataclass

from .subject import Refusal, Subject


@dataclass(frozen=True, slots=True)
class VerificationRail:
    subject: Subject
    name: str
    family: str
    domain: str
    toolchain: str
    config_digest: str

    def __post_init__(self) -> None:
        for value in (self.name, self.family, self.domain, self.toolchain, self.config_digest):
            if not value or "\n" in value:
                raise Refusal("REFUSED_INVALID_RAIL_IDENTITY")

    @property
    def fingerprint(self) -> str:
        body = {
            "subject": self.subject.identity,
            "name": self.name,
            "family": self.family,
            "domain": self.domain,
            "toolchain": self.toolchain,
            "config_digest": self.config_digest,
        }
        return hashlib.sha256(
            json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
