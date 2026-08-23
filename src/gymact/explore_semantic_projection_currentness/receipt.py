from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from .subject import Refusal, Subject


@dataclass(frozen=True, slots=True)
class ProjectionReceipt:
    subject: Subject
    semantic_iri: str
    selected_fingerprint: str
    selector: str
    epoch_token: str
    storage: str
    standing: str
    actuation_performed: bool = False
    schema: str = "gymact.explore-semantic-projection-currentness/1"

    def __post_init__(self) -> None:
        if self.actuation_performed:
            raise Refusal("REFUSED_UNRECEIPTED_ACTUATION")

    def body(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "subject": self.subject.identity,
            "semantic_iri": self.semantic_iri,
            "selected_fingerprint": self.selected_fingerprint,
            "selector": self.selector,
            "epoch_token": self.epoch_token,
            "storage": self.storage,
            "standing": self.standing,
            "actuation_performed": self.actuation_performed,
        }

    @property
    def digest(self) -> str:
        return hashlib.sha256(
            json.dumps(self.body(), sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    def replay(self, expected_digest: str) -> bool:
        return self.digest == expected_digest


def require_do() -> None:
    raise Refusal("REFUSED_UNRECEIPTED_ACTUATION")
