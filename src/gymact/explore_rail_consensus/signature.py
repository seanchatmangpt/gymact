from dataclasses import dataclass
import hashlib, json, re

from .subject import Refusal

_VOLATILE = re.compile(r"(?:0x[0-9a-fA-F]+|\b\d{6,}\b|/home/runner/work/[^\s]+)")

@dataclass(frozen=True, slots=True)
class FailureSignature:
    stage: str
    code: str
    normalized_message: str

    @classmethod
    def from_failure(cls, stage: str, code: str, message: str) -> "FailureSignature":
        if not stage or not code or not message.strip():
            raise Refusal("REFUSED_INVALID_FAILURE_SIGNATURE")
        normalized = _VOLATILE.sub("<volatile>", " ".join(message.split()))
        return cls(stage=stage, code=code, normalized_message=normalized)

    @property
    def digest(self) -> str:
        payload = [self.stage, self.code, self.normalized_message]
        return hashlib.sha256(json.dumps(payload, separators=(",", ":")).encode()).hexdigest()
