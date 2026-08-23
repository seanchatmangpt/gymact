from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum

from .semantic_type import SemanticType
from .subject import Refusal


class RepresentationKind(StrEnum):
    RDF_TERM = "RDF_TERM"
    ASH_PROJECTION = "ASH_PROJECTION"
    WASM_CARRIER = "WASM_CARRIER"
    CANONICAL_JSON = "CANONICAL_JSON"


@dataclass(frozen=True, slots=True)
class RepresentationCandidate:
    semantic_type: SemanticType
    kind: RepresentationKind
    schema: tuple[tuple[str, str], ...]
    reversible: bool
    migration_cost: int
    runtime_cost: int

    def __post_init__(self) -> None:
        if self.migration_cost < 0 or self.runtime_cost < 0:
            raise Refusal("REFUSED_NEGATIVE_REPRESENTATION_COST")
        names = [name for name, _ in self.schema]
        if not names or len(names) != len(set(names)):
            raise Refusal("REFUSED_INVALID_REPRESENTATION_SCHEMA")

    @property
    def fingerprint(self) -> str:
        payload = {
            "semantic": self.semantic_type.identity,
            "kind": self.kind.value,
            "schema": self.schema,
            "reversible": self.reversible,
            "migration_cost": self.migration_cost,
            "runtime_cost": self.runtime_cost,
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
