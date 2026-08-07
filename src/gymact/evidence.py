"""Tamper-evident receipt ledgers and public evidence projections."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol, runtime_checkable

import anyio
from blake3 import blake3
from rdflib import DCTERMS, RDF, XSD, Graph, Literal, Namespace, URIRef

from gymact.models import Operation, Receipt, VerificationResult

PROV = Namespace("http://www.w3.org/ns/prov#")
SOSA = Namespace("http://www.w3.org/ns/sosa/")
EARL = Namespace("http://www.w3.org/ns/earl#")


def canonical_json_bytes(value: object) -> bytes:
    """Return deterministic UTF-8 JSON suitable for hashing and size gates."""
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def digest_json(value: object) -> str:
    """Return the BLAKE3 digest of a JSON-compatible value."""
    return blake3(canonical_json_bytes(value)).hexdigest()


def digest_text(value: str) -> str:
    """Hash provider/authority details without storing those details in receipts."""
    return blake3(value.encode("utf-8", errors="replace")).hexdigest()


def _stamp(receipt: Receipt, previous: str | None) -> Receipt:
    unsigned = receipt.model_copy(
        update={
            "occurred_at": receipt.occurred_at or datetime.now(UTC),
            "previous_receipt_digest": previous,
            "receipt_digest": None,
        }
    )
    digest = digest_json(unsigned.model_dump(mode="json", exclude={"receipt_digest"}))
    return unsigned.model_copy(update={"receipt_digest": digest})


def verify_receipt_chain(receipts: tuple[Receipt, ...]) -> bool:
    """Verify ordering, links, and every BLAKE3 receipt digest."""
    previous: str | None = None
    for receipt in receipts:
        if receipt.previous_receipt_digest != previous or receipt.receipt_digest is None:
            return False
        unsigned = receipt.model_copy(update={"receipt_digest": None})
        expected = digest_json(unsigned.model_dump(mode="json", exclude={"receipt_digest"}))
        if expected != receipt.receipt_digest:
            return False
        previous = receipt.receipt_digest
    return True


@runtime_checkable
class ReceiptLedger(Protocol):
    """Append-only evidence ledger contract."""

    async def append(self, receipt: Receipt) -> Receipt: ...

    async def receipts(self, episode_id: str | None = None) -> tuple[Receipt, ...]: ...

    async def verify_chain(self) -> bool: ...


class MemoryReceiptLedger:
    """In-memory BLAKE3 chain for tests and ephemeral local gyms."""

    def __init__(self) -> None:
        self._items: list[Receipt] = []
        self._lock = anyio.Lock()

    async def append(self, receipt: Receipt) -> Receipt:
        async with self._lock:
            previous = self._items[-1].receipt_digest if self._items else None
            stamped = _stamp(receipt, previous)
            self._items.append(stamped)
            return stamped

    async def receipts(self, episode_id: str | None = None) -> tuple[Receipt, ...]:
        async with self._lock:
            if episode_id is None:
                return tuple(self._items)
            return tuple(item for item in self._items if item.episode_id == episode_id)

    async def verify_chain(self) -> bool:
        async with self._lock:
            return verify_receipt_chain(tuple(self._items))


class SQLiteReceiptLedger:
    """Durable append-only SQLite chain using WAL and FULL synchronization."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = anyio.Lock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10.0)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS receipts (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    episode_id TEXT NOT NULL,
                    receipt_digest TEXT NOT NULL UNIQUE,
                    payload_json TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_receipts_episode ON receipts(episode_id, seq)"
            )

    def _append_sync(self, receipt: Receipt) -> Receipt:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT receipt_digest FROM receipts ORDER BY seq DESC LIMIT 1"
            ).fetchone()
            stamped = _stamp(receipt, str(row[0]) if row else None)
            assert stamped.receipt_digest is not None
            connection.execute(
                "INSERT INTO receipts(episode_id, receipt_digest, payload_json) VALUES (?, ?, ?)",
                (stamped.episode_id, stamped.receipt_digest, stamped.model_dump_json()),
            )
            connection.commit()
            return stamped
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _receipts_sync(self, episode_id: str | None) -> tuple[Receipt, ...]:
        with self._connect() as connection:
            if episode_id is None:
                rows = connection.execute(
                    "SELECT payload_json FROM receipts ORDER BY seq"
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT payload_json FROM receipts WHERE episode_id = ? ORDER BY seq",
                    (episode_id,),
                ).fetchall()
        return tuple(Receipt.model_validate_json(str(row[0])) for row in rows)

    async def append(self, receipt: Receipt) -> Receipt:
        async with self._lock:
            return await anyio.to_thread.run_sync(self._append_sync, receipt)

    async def receipts(self, episode_id: str | None = None) -> tuple[Receipt, ...]:
        return await anyio.to_thread.run_sync(self._receipts_sync, episode_id)

    async def verify_chain(self) -> bool:
        return verify_receipt_chain(await self.receipts())


def receipts_to_prov(receipts: tuple[Receipt, ...]) -> Graph:
    """Project receipt evidence into public PROV-O/SOSA semantics."""
    graph = Graph()
    graph.bind("prov", PROV)
    graph.bind("sosa", SOSA)
    graph.bind("dct", DCTERMS)
    for receipt in receipts:
        receipt_uri = URIRef(f"urn:gymact:receipt:{receipt.receipt_id}")
        activity_uri = URIRef(f"urn:gymact:activity:{receipt.receipt_id}")
        episode_uri = URIRef(f"urn:gymact:episode:{receipt.episode_id}")
        graph.add((receipt_uri, RDF.type, PROV.Entity))
        graph.add((activity_uri, RDF.type, PROV.Activity))
        graph.add((episode_uri, RDF.type, PROV.Activity))
        graph.add((receipt_uri, PROV.wasGeneratedBy, activity_uri))
        graph.add((activity_uri, PROV.wasInformedBy, episode_uri))
        graph.add((receipt_uri, DCTERMS.identifier, Literal(receipt.receipt_id)))
        standing = receipt.standing.value.lower().replace("_", "-")
        graph.add((receipt_uri, DCTERMS.type, URIRef(f"urn:gymact:standing:{standing}")))
        graph.add((receipt_uri, PROV.value, Literal(receipt.stage.value)))
        if receipt.occurred_at is not None:
            graph.add(
                (
                    receipt_uri,
                    PROV.generatedAtTime,
                    Literal(receipt.occurred_at.isoformat(), datatype=XSD.dateTime),
                )
            )
        if receipt.operation in {Operation.ACT, Operation.RESTORE, Operation.TEARDOWN}:
            graph.add((activity_uri, RDF.type, SOSA.Actuation))
        if receipt.subject_ref:
            graph.add((activity_uri, PROV.used, URIRef(receipt.subject_ref)))
        if receipt.capability_ref:
            graph.add((activity_uri, SOSA.usedProcedure, URIRef(receipt.capability_ref)))
        if receipt.pre_state_digest:
            pre = URIRef(f"urn:blake3:{receipt.pre_state_digest}")
            graph.add((pre, RDF.type, PROV.Entity))
            graph.add((activity_uri, PROV.used, pre))
        if receipt.post_state_digest:
            post = URIRef(f"urn:blake3:{receipt.post_state_digest}")
            graph.add((post, RDF.type, PROV.Entity))
            graph.add((post, PROV.wasGeneratedBy, activity_uri))
        if receipt.authority_evidence_ref:
            graph.add((activity_uri, PROV.used, URIRef(receipt.authority_evidence_ref)))
        derived = receipt.prepared_receipt_digest or receipt.previous_receipt_digest
        if derived:
            graph.add((receipt_uri, PROV.wasDerivedFrom, URIRef(f"urn:blake3:{derived}")))
    return graph


def verification_to_earl(result: VerificationResult) -> Graph:
    """Project an independent verification result into EARL."""
    graph = Graph()
    graph.bind("earl", EARL)
    assertion = URIRef(f"urn:gymact:verification:{result.verification_id}:assertion")
    test_result = URIRef(f"urn:gymact:verification:{result.verification_id}:result")
    test = URIRef(f"urn:gymact:verification:{result.verification_id}:criterion")
    subject = URIRef(f"urn:gymact:episode:{result.episode_id}")
    graph.add((assertion, RDF.type, EARL.Assertion))
    graph.add((assertion, EARL.assertedBy, URIRef("urn:gymact:verifier:runtime")))
    graph.add((assertion, EARL.subject, subject))
    graph.add((assertion, EARL.test, test))
    graph.add((assertion, EARL.result, test_result))
    graph.add((test_result, RDF.type, EARL.TestResult))
    graph.add((test_result, EARL.outcome, EARL.passed if result.passed else EARL.failed))
    return graph
