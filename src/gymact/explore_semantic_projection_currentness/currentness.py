from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from .subject import Refusal, Subject


@dataclass(frozen=True, slots=True)
class ProjectionEpoch:
    subject: Subject
    generation: int
    semantic_digest: str
    projection_digest: str

    def __post_init__(self) -> None:
        if self.generation < 0:
            raise Refusal("REFUSED_NEGATIVE_GENERATION")
        for digest in (self.semantic_digest, self.projection_digest):
            if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
                raise Refusal("REFUSED_INVALID_PROJECTION_DIGEST")

    @property
    def token(self) -> str:
        payload = (
            self.subject.identity,
            self.generation,
            self.semantic_digest,
            self.projection_digest,
        )
        return hashlib.sha256(json.dumps(payload, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class Transition:
    expected_token: str
    before: ProjectionEpoch
    after: ProjectionEpoch

    def admit(self, current: ProjectionEpoch) -> ProjectionEpoch:
        if current.token != self.expected_token or current.token != self.before.token:
            raise Refusal("REFUSED_STALE_PROJECTION_CAS")
        if self.after.generation <= self.before.generation:
            raise Refusal("REFUSED_NONMONOTONE_PROJECTION_GENERATION")
        return self.after


def detects_aba(history: tuple[ProjectionEpoch, ...]) -> bool:
    seen: dict[str, int] = {}
    for epoch in history:
        key = epoch.projection_digest
        if key in seen and seen[key] != epoch.generation:
            return True
        seen[key] = epoch.generation
    return False
