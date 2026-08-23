from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from .clock import VectorClock
from .refusal import Refused
from .subject import Subject

_HEX64 = re.compile(r"^[0-9a-f]{64}$")

class Representation(StrEnum):
    RDF_TERM = "RDF_TERM"
    ASH_PROJECTION = "ASH_PROJECTION"
    WASM_CARRIER = "WASM_CARRIER"
    CANONICAL_JSON = "CANONICAL_JSON"

@dataclass(frozen=True, slots=True)
class ReplicaProjection:
    subject: Subject
    replica_id: str
    generation: int
    semantic_digest: str
    projection_digest: str
    representation: Representation
    clock: VectorClock
    observed_at: datetime

    def __post_init__(self) -> None:
        if not self.replica_id or "\n" in self.replica_id:
            raise Refused("REFUSED_INVALID_REPLICA_ID")
        if self.generation < 0:
            raise Refused("REFUSED_INVALID_GENERATION")
        if not _HEX64.fullmatch(self.semantic_digest) or not _HEX64.fullmatch(self.projection_digest):
            raise Refused("REFUSED_INVALID_PROJECTION_DIGEST")
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise Refused("REFUSED_NAIVE_OBSERVATION_TIME")

    @property
    def fingerprint(self) -> str:
        body = {
            "clock": self.clock.entries,
            "generation": self.generation,
            "observed_at": self.observed_at.isoformat(),
            "projection_digest": self.projection_digest,
            "replica_id": self.replica_id,
            "representation": self.representation.value,
            "semantic_digest": self.semantic_digest,
            "subject": self.subject.value,
        }
        raw = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(raw).hexdigest()
