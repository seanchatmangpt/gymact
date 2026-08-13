"""Typed RDF source inputs for deterministic semantic ingestion."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from pathlib import Path


class SemanticRefusal(RuntimeError):
    """Base class for fail-closed semantic input refusals."""


class UnsupportedFormatRefusal(SemanticRefusal):
    pass


class SourceDriftRefusal(SemanticRefusal):
    pass


class SchemaRefusal(SemanticRefusal):
    pass


class ContractRefusal(SemanticRefusal):
    pass


class RDFFormat(str, Enum):
    TURTLE = "turtle"
    RDF_XML = "xml"
    JSON_LD = "json-ld"

    @classmethod
    def from_path(cls, path: Path) -> "RDFFormat":
        formats = {
            ".ttl": cls.TURTLE,
            ".rdf": cls.RDF_XML,
            ".xml": cls.RDF_XML,
            ".jsonld": cls.JSON_LD,
            ".json-ld": cls.JSON_LD,
        }
        try:
            return formats[path.suffix.lower()]
        except KeyError as exc:
            raise UnsupportedFormatRefusal(f"unsupported RDF format: {path.name}") from exc


@dataclass(frozen=True)
class RDFSource:
    source_id: str
    source_uri: str
    format: RDFFormat
    content: bytes
    expected_sha256: str | None = None

    @property
    def digest(self) -> str:
        return sha256(self.content).hexdigest()

    def verify(self) -> None:
        if not self.source_id.strip() or not self.source_uri.strip():
            raise SchemaRefusal("source_id and source_uri must be non-empty")
        if self.expected_sha256 is not None and self.digest != self.expected_sha256:
            raise SourceDriftRefusal(
                f"source drift: expected {self.expected_sha256}, observed {self.digest}"
            )

    @classmethod
    def from_path(
        cls,
        path: Path,
        *,
        source_id: str | None = None,
        source_uri: str | None = None,
        expected_sha256: str | None = None,
    ) -> "RDFSource":
        return cls(
            source_id=source_id or path.name,
            source_uri=source_uri or path.resolve().as_uri(),
            format=RDFFormat.from_path(path),
            content=path.read_bytes(),
            expected_sha256=expected_sha256,
        )
