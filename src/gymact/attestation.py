"""Authenticated checkpoints for portable GymAct evidence chains.

The receipt ledger already makes mutation evident with a BLAKE3 hash chain.
This module adds origin authentication at export/checkpoint boundaries without
coupling GymAct to a specific cloud KMS, HSM, PKI, or signature library.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
from collections.abc import Iterable
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from gymact.evidence import EvidenceRecord, MemoryReceiptLedger, canonical_bytes

CHECKPOINT_VERSION = "gymact-evidence-checkpoint/1"


class EvidenceCheckpoint(BaseModel):
    """Portable authenticator over one complete receipt-chain prefix."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    version: str = CHECKPOINT_VERSION
    record_count: int = Field(ge=1)
    chain_tip: str
    algorithm: str
    key_id: str
    signature: str


@runtime_checkable
class EvidenceCheckpointSigner(Protocol):
    """Signing seam for a local key, HSM, cloud KMS, or remote signer."""

    @property
    def algorithm(self) -> str: ...

    @property
    def key_id(self) -> str: ...

    def sign(self, payload: bytes) -> bytes: ...


@runtime_checkable
class EvidenceCheckpointVerifier(Protocol):
    """Verification seam paired with :class:`EvidenceCheckpointSigner`."""

    @property
    def algorithm(self) -> str: ...

    @property
    def key_id(self) -> str: ...

    def verify(self, payload: bytes, signature: bytes) -> bool: ...


class HmacSha256CheckpointKey:
    """Dependency-free reference authenticator for shared-secret deployments.

    Enterprise deployments that require asymmetric non-repudiation should
    implement the signer/verifier protocols with their KMS/HSM. The checkpoint
    format intentionally does not make HMAC look like a public-key signature.
    """

    algorithm = "HMAC-SHA256"

    def __init__(self, *, key_id: str, secret: bytes) -> None:
        if not key_id.strip():
            raise ValueError("EMPTY_CHECKPOINT_KEY_ID")
        if len(secret) < 32:
            raise ValueError("CHECKPOINT_HMAC_KEY_TOO_SHORT")
        self._key_id = key_id
        self._secret = bytes(secret)

    @property
    def key_id(self) -> str:
        return self._key_id

    def sign(self, payload: bytes) -> bytes:
        return hmac.new(self._secret, payload, hashlib.sha256).digest()

    def verify(self, payload: bytes, signature: bytes) -> bool:
        expected = self.sign(payload)
        return hmac.compare_digest(expected, signature)


def _records_tuple(records: Iterable[EvidenceRecord]) -> tuple[EvidenceRecord, ...]:
    materialized = tuple(records)
    if not materialized:
        raise ValueError("EMPTY_EVIDENCE_CHAIN")
    return materialized


def _chain_is_valid(records: tuple[EvidenceRecord, ...]) -> bool:
    replay = MemoryReceiptLedger()
    for record in records:
        generated = replay.append(record.receipt)
        if generated != record:
            return False
    return replay.verify()


def checkpoint_payload(
    *,
    record_count: int,
    chain_tip: str,
    algorithm: str,
    key_id: str,
) -> bytes:
    """Return the RFC 8785 payload authenticated by every checkpoint."""
    return canonical_bytes(
        {
            "algorithm": algorithm,
            "chain_tip": chain_tip,
            "key_id": key_id,
            "record_count": record_count,
            "version": CHECKPOINT_VERSION,
        }
    )


def create_evidence_checkpoint(
    records: Iterable[EvidenceRecord],
    signer: EvidenceCheckpointSigner,
) -> EvidenceCheckpoint:
    """Authenticate a verified chain prefix with one signer operation.

    Signing a single chain tip keeps KMS/HSM traffic O(checkpoints), not
    O(receipts), while the existing chain binds every preceding receipt.
    """
    materialized = _records_tuple(records)
    if not _chain_is_valid(materialized):
        raise ValueError("INVALID_EVIDENCE_CHAIN")
    tip = materialized[-1].record_digest
    payload = checkpoint_payload(
        record_count=len(materialized),
        chain_tip=tip,
        algorithm=signer.algorithm,
        key_id=signer.key_id,
    )
    signature = base64.urlsafe_b64encode(signer.sign(payload)).decode("ascii").rstrip("=")
    return EvidenceCheckpoint(
        record_count=len(materialized),
        chain_tip=tip,
        algorithm=signer.algorithm,
        key_id=signer.key_id,
        signature=signature,
    )


def verify_evidence_checkpoint(
    records: Iterable[EvidenceRecord],
    checkpoint: EvidenceCheckpoint,
    verifier: EvidenceCheckpointVerifier,
) -> bool:
    """Verify chain integrity, checkpoint scope, signer identity, and authenticator."""
    try:
        materialized = _records_tuple(records)
    except ValueError:
        return False
    if not _chain_is_valid(materialized):
        return False
    if checkpoint.version != CHECKPOINT_VERSION:
        return False
    if checkpoint.record_count != len(materialized):
        return False
    if checkpoint.chain_tip != materialized[-1].record_digest:
        return False
    if checkpoint.algorithm != verifier.algorithm or checkpoint.key_id != verifier.key_id:
        return False

    payload = checkpoint_payload(
        record_count=checkpoint.record_count,
        chain_tip=checkpoint.chain_tip,
        algorithm=checkpoint.algorithm,
        key_id=checkpoint.key_id,
    )
    try:
        padding = "=" * (-len(checkpoint.signature) % 4)
        signature = base64.b64decode(
            checkpoint.signature + padding,
            altchars=b"-_",
            validate=True,
        )
    except (ValueError, TypeError):
        return False
    return verifier.verify(payload, signature)
