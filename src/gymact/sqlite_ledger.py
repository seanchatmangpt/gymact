"""Durable transactional receipt ledger backed by Python's stdlib SQLite."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from threading import RLock

from gymact.evidence import EvidenceRecord, _same_intent, canonical_bytes, digest
from gymact.models import Receipt


class SQLiteReceiptLedger:
    """Single-process durable BLAKE3 receipt chain with SQLite WAL durability.

    SQLite provides atomic commits and crash recovery. `BEGIN IMMEDIATE` serializes
    writers for one database file; callers needing distributed/multi-region anchoring
    should inject a ledger implementation backed by their authority/evidence system.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._connection = sqlite3.connect(self.path, timeout=30.0, check_same_thread=False)
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA synchronous=FULL")
        self._connection.execute("PRAGMA foreign_keys=ON")
        self._connection.execute("PRAGMA busy_timeout=30000")
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS receipt_evidence (
                sequence INTEGER PRIMARY KEY,
                receipt_id TEXT NOT NULL UNIQUE,
                previous_digest TEXT,
                receipt_digest TEXT NOT NULL,
                record_digest TEXT NOT NULL UNIQUE,
                receipt_json TEXT NOT NULL
            )
            """
        )
        self._connection.commit()
        if not self.verify():
            self._connection.close()
            raise ValueError("EVIDENCE_CHAIN_INVALID")

    @staticmethod
    def _record_digest(sequence: int, previous_digest: str | None, receipt_digest: str) -> str:
        return digest(
            {
                "sequence": sequence,
                "previous_digest": previous_digest,
                "receipt_digest": receipt_digest,
            }
        )

    @staticmethod
    def _record(row: tuple[object, ...]) -> EvidenceRecord:
        sequence, previous_digest, receipt_digest, record_digest, receipt_json = row
        receipt = Receipt.model_validate(json.loads(str(receipt_json)))
        return EvidenceRecord(
            sequence=int(sequence),
            previous_digest=None if previous_digest is None else str(previous_digest),
            receipt_digest=str(receipt_digest),
            record_digest=str(record_digest),
            receipt=receipt,
        )

    def append(self, receipt: Receipt) -> EvidenceRecord:
        """Atomically append a receipt; replay of the same receipt id is idempotent."""
        payload = receipt.model_dump(mode="json")
        receipt_json = canonical_bytes(payload).decode("utf-8")
        receipt_digest = digest(payload)
        with self._lock:
            try:
                self._connection.execute("BEGIN IMMEDIATE")
                existing = self._connection.execute(
                    """
                    SELECT sequence, previous_digest, receipt_digest, record_digest, receipt_json
                    FROM receipt_evidence WHERE receipt_id = ?
                    """,
                    (receipt.receipt_id,),
                ).fetchone()
                if existing is not None:
                    prior = self._record(existing)
                    if prior.receipt != receipt:
                        raise ValueError("RECEIPT_ID_CONFLICT")
                    self._connection.commit()
                    return prior

                if receipt.idempotency_key is not None:
                    # json_extract over receipt_json avoids a schema migration
                    # for existing database files (see MemoryReceiptLedger's
                    # in-memory equivalent for the field-set rationale --
                    # excludes lineage/combinatorial-binding fields so cut.py's
                    # legitimate re-receipting flow is never falsely refused).
                    key_row = self._connection.execute(
                        """
                        SELECT sequence, previous_digest, receipt_digest, record_digest, receipt_json
                        FROM receipt_evidence
                        WHERE json_extract(receipt_json, '$.idempotency_key') = ?
                        ORDER BY sequence ASC LIMIT 1
                        """,
                        (receipt.idempotency_key,),
                    ).fetchone()
                    if key_row is not None:
                        key_prior = self._record(key_row)
                        if not _same_intent(key_prior.receipt, receipt):
                            raise ValueError("IDEMPOTENCY_KEY_REUSE_WITH_DIFFERENT_INTENT")

                last = self._connection.execute(
                    "SELECT sequence, record_digest FROM receipt_evidence "
                    "ORDER BY sequence DESC LIMIT 1"
                ).fetchone()
                sequence = 0 if last is None else int(last[0]) + 1
                previous = None if last is None else str(last[1])
                record_digest = self._record_digest(sequence, previous, receipt_digest)
                self._connection.execute(
                    """
                    INSERT INTO receipt_evidence (
                        sequence, receipt_id, previous_digest, receipt_digest,
                        record_digest, receipt_json
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        sequence,
                        receipt.receipt_id,
                        previous,
                        receipt_digest,
                        record_digest,
                        receipt_json,
                    ),
                )
                self._connection.commit()
            except Exception:
                self._connection.rollback()
                raise
        return EvidenceRecord(
            sequence=sequence,
            previous_digest=previous,
            receipt_digest=receipt_digest,
            record_digest=record_digest,
            receipt=receipt,
        )

    def records(self) -> tuple[EvidenceRecord, ...]:
        """Return records in causal chain order."""
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT sequence, previous_digest, receipt_digest, record_digest, receipt_json
                FROM receipt_evidence ORDER BY sequence ASC
                """
            ).fetchall()
        return tuple(self._record(row) for row in rows)

    def find(self, receipt_id: str) -> EvidenceRecord | None:
        """Resolve one receipt id without scanning the ledger."""
        with self._lock:
            row = self._connection.execute(
                """
                SELECT sequence, previous_digest, receipt_digest, record_digest, receipt_json
                FROM receipt_evidence WHERE receipt_id = ?
                """,
                (receipt_id,),
            ).fetchone()
        return None if row is None else self._record(row)

    def verify(self) -> bool:
        """Verify sequence, previous links, receipt hashes and record hashes."""
        previous: str | None = None
        for sequence, record in enumerate(self.records()):
            if record.sequence != sequence or record.previous_digest != previous:
                return False
            expected_receipt = digest(record.receipt.model_dump(mode="json"))
            if record.receipt_digest != expected_receipt:
                return False
            expected_record = self._record_digest(sequence, previous, expected_receipt)
            if record.record_digest != expected_record:
                return False
            previous = record.record_digest
        return True

    def close(self) -> None:
        """Flush and close the SQLite connection."""
        with self._lock:
            self._connection.commit()
            self._connection.close()

    def __enter__(self) -> SQLiteReceiptLedger:
        return self

    def __exit__(self, *args: object) -> None:
        del args
        self.close()
