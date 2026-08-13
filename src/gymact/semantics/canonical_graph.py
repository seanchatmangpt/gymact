"""Canonical RDF graph construction with provenance and deterministic identity."""

from __future__ import annotations

import warnings
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from rdflib import Graph, URIRef
from rdflib.compare import to_canonical_graph

from gymact.semantics.rdf_source import ContractRefusal, RDFFormat, RDFSource, SchemaRefusal


@dataclass(frozen=True)
class SourceProvenance:
    source_id: str
    source_uri: str
    format: RDFFormat
    sha256: str
    triple_count: int


@dataclass(frozen=True)
class CanonicalGraph:
    graph: Graph
    canonical_ntriples: bytes
    digest: str
    provenance: tuple[SourceProvenance, ...]
    subject_sources: Mapping[str, tuple[str, ...]]

    @property
    def triple_count(self) -> int:
        return len(self.graph)


def _canonical_bytes(graph: Graph) -> bytes:
    serialized = to_canonical_graph(graph).serialize(format="nt")
    text = serialized.decode() if isinstance(serialized, bytes) else serialized
    lines = sorted(line.strip() for line in text.splitlines() if line.strip())
    return ("\n".join(lines) + ("\n" if lines else "")).encode()


def ingest(sources: Sequence[RDFSource]) -> CanonicalGraph:
    if not sources:
        raise SchemaRefusal("at least one RDF source is required")
    ids = [source.source_id for source in sources]
    if len(ids) != len(set(ids)):
        raise ContractRefusal("source_id uniqueness violation")

    merged = Graph()
    provenance: list[SourceProvenance] = []
    subject_sources: dict[str, set[str]] = {}
    for source in sources:
        source.verify()
        parsed = Graph()
        try:
            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore",
                    message="ConjunctiveGraph is deprecated, use Dataset instead.*",
                    category=DeprecationWarning,
                    module=r"rdflib\.plugins\.parsers\.jsonld",
                )
                parsed.parse(
                    data=source.content,
                    format=source.format.value,
                    publicID=source.source_uri,
                )
        except Exception as exc:
            raise SchemaRefusal(f"RDF parse failed for {source.source_id}: {exc}") from exc
        for triple in parsed:
            merged.add(triple)
            if isinstance(triple[0], URIRef):
                subject_sources.setdefault(str(triple[0]), set()).add(source.source_id)
        provenance.append(
            SourceProvenance(
                source.source_id,
                source.source_uri,
                source.format,
                source.digest,
                len(parsed),
            )
        )

    canonical = _canonical_bytes(merged)
    return CanonicalGraph(
        merged,
        canonical,
        sha256(canonical).hexdigest(),
        tuple(sorted(provenance, key=lambda item: item.source_id)),
        {
            subject: tuple(sorted(source_ids))
            for subject, source_ids in sorted(subject_sources.items())
        },
    )


def ingest_paths(paths: Iterable[Path]) -> CanonicalGraph:
    ordered = tuple(sorted((Path(path) for path in paths), key=str))
    return ingest(tuple(RDFSource.from_path(path) for path in ordered))
