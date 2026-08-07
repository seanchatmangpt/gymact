"""Tamper-evident evidence and public PROV/EARL projections."""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Protocol, runtime_checkable

from blake3 import blake3
from pydantic import BaseModel, ConfigDict
from rdflib import BNode, Graph, Literal, Namespace, RDF, URIRef
from rdflib.namespace import DCTERMS

from gymact.models import Receipt, VerificationResult

PROV = Namespace("http://www.w3.org/ns/prov#")
EARL = Namespace("http://www.w3.org/ns/earl#")
SOSA = Namespace("http://www.w3.org/ns/sosa/")


def canonical_bytes(value: object) -> bytes:
    """Encode one value deterministically for hashing and size admission."""
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")


def digest(value: object) -> str:
    """Return a BLAKE3-256 hex digest over canonical JSON."""
    return blake3(canonical_bytes(value)).hexdigest()


class EvidenceRecord(BaseModel):
    """One append-only, hash-chained receipt record."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    sequence: int
    previous_digest: str | None
    receipt_digest: str
    record_digest: str
    receipt: Receipt


@runtime_checkable
class ReceiptLedger(Protocol):
    """Minimal append-only receipt-ledger contract."""

    def append(self, receipt: Receipt) -> EvidenceRecord: ...
    def records(self) -> tuple[EvidenceRecord, ...]: ...
    def verify(self) -> bool: ...
    def find(self, receipt_id: str) -> EvidenceRecord | None: ...


class MemoryReceiptLedger:
    """Deterministic in-memory BLAKE3 chain used by the reference runtime.

    Production deployments can inject a durable implementation without changing
    GymAct semantics. Re-appending the same receipt id is idempotent.
    """

    def __init__(self) -> None:
        self._records: list[EvidenceRecord] = []
        self._by_receipt: dict[str, EvidenceRecord] = {}

    @staticmethod
    def _record_digest(sequence: int, previous_digest: str | None, receipt_digest: str) -> str:
        return digest(
            {
                "sequence": sequence,
                "previous_digest": previous_digest,
                "receipt_digest": receipt_digest,
            }
        )

    def append(self, receipt: Receipt) -> EvidenceRecord:
        prior = self._by_receipt.get(receipt.receipt_id)
        if prior is not None:
            if prior.receipt != receipt:
                raise ValueError("RECEIPT_ID_CONFLICT")
            return prior
        sequence = len(self._records)
        previous = self._records[-1].record_digest if self._records else None
        receipt_digest = digest(receipt.model_dump(mode="json"))
        record = EvidenceRecord(
            sequence=sequence,
            previous_digest=previous,
            receipt_digest=receipt_digest,
            record_digest=self._record_digest(sequence, previous, receipt_digest),
            receipt=receipt,
        )
        self._records.append(record)
        self._by_receipt[receipt.receipt_id] = record
        return record

    def records(self) -> tuple[EvidenceRecord, ...]:
        return tuple(self._records)

    def find(self, receipt_id: str) -> EvidenceRecord | None:
        return self._by_receipt.get(receipt_id)

    def verify(self) -> bool:
        previous: str | None = None
        for sequence, record in enumerate(self._records):
            if record.sequence != sequence or record.previous_digest != previous:
                return False
            expected_receipt = digest(record.receipt.model_dump(mode="json"))
            if record.receipt_digest != expected_receipt:
                return False
            expected_record = self._record_digest(
                record.sequence,
                record.previous_digest,
                record.receipt_digest,
            )
            if record.record_digest != expected_record:
                return False
            previous = record.record_digest
        return True


def evidence_graph(
    records: Iterable[EvidenceRecord],
    verifications: Iterable[VerificationResult] = (),
) -> Graph:
    """Project runtime evidence to public PROV-O, SOSA, EARL and DCTERMS RDF."""
    graph = Graph()
    graph.bind("prov", PROV)
    graph.bind("earl", EARL)
    graph.bind("sosa", SOSA)
    graph.bind("dct", DCTERMS)

    for record in records:
        receipt = record.receipt
        receipt_ref = URIRef(f"urn:gymact:receipt:{receipt.receipt_id}")
        activity_ref = URIRef(f"urn:gymact:activity:{receipt.receipt_id}")
        episode_ref = URIRef(f"urn:gymact:episode:{receipt.episode_id}")
        graph.add((receipt_ref, RDF.type, PROV.Entity))
        graph.add((activity_ref, RDF.type, PROV.Activity))
        graph.add((episode_ref, RDF.type, PROV.Activity))
        graph.add((receipt_ref, PROV.wasGeneratedBy, activity_ref))
        graph.add((activity_ref, PROV.wasInformedBy, episode_ref))
        graph.add((receipt_ref, DCTERMS.identifier, Literal(record.record_digest)))
        graph.add((receipt_ref, DCTERMS.type, Literal(receipt.standing.value)))
        graph.add((activity_ref, DCTERMS.type, Literal(receipt.operation.value)))
        if receipt.subject_ref:
            graph.add((activity_ref, PROV.used, URIRef(receipt.subject_ref)))
        if receipt.capability_ref:
            graph.add((activity_ref, PROV.used, URIRef(receipt.capability_ref)))
        if receipt.authority_evidence_ref:
            graph.add((activity_ref, PROV.used, URIRef(receipt.authority_evidence_ref)))

    for verification in verifications:
        assertion = URIRef(f"urn:gymact:verification:{verification.verification_id}")
        result = BNode()
        episode_ref = URIRef(f"urn:gymact:episode:{verification.episode_id}")
        graph.add((assertion, RDF.type, EARL.Assertion))
        graph.add((assertion, EARL.assertedBy, URIRef("urn:gymact:verifier:runtime")))
        graph.add((assertion, EARL.subject, episode_ref))
        graph.add((assertion, EARL.result, result))
        graph.add((result, RDF.type, EARL.TestResult))
        graph.add((result, EARL.outcome, EARL.passed if verification.passed else EARL.failed))
        graph.add((result, DCTERMS.identifier, Literal(verification.state_digest)))
    return graph
