from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from .subject import Refusal


class TermKind(StrEnum):
    IRI = "IRI"
    LITERAL = "LITERAL"
    NODE = "NODE"


_IRI = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:[^\s]+$")


@dataclass(frozen=True, slots=True)
class SemanticType:
    iri: str
    term_kind: TermKind
    constraints_digest: str
    unit_iri: str | None = None
    time_iri: str | None = None

    def __post_init__(self) -> None:
        if not _IRI.fullmatch(self.iri):
            raise Refusal("REFUSED_INVALID_SEMANTIC_IRI")
        digest_is_invalid = len(self.constraints_digest) != 64 or any(
            c not in "0123456789abcdef" for c in self.constraints_digest
        )
        if digest_is_invalid:
            raise Refusal("REFUSED_INVALID_CONSTRAINT_DIGEST")
        for value in (self.unit_iri, self.time_iri):
            if value is not None and not _IRI.fullmatch(value):
                raise Refusal("REFUSED_INVALID_SEMANTIC_IRI")

    @property
    def identity(self) -> tuple[str, str, str, str | None, str | None]:
        return (
            self.iri,
            self.term_kind.value,
            self.constraints_digest,
            self.unit_iri,
            self.time_iri,
        )
