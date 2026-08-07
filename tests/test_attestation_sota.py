from __future__ import annotations

import pytest

from gymact.attestation import (
    CHECKPOINT_VERSION,
    HmacSha256CheckpointKey,
    checkpoint_payload,
    create_evidence_checkpoint,
    verify_evidence_checkpoint,
)
from gymact.evidence import MemoryReceiptLedger
from gymact.models import Operation, Receipt, Standing


def _records():  # type: ignore[no-untyped-def]
    ledger = MemoryReceiptLedger()
    ledger.append(
        Receipt(
            receipt_id="receipt-1",
            occurred_at="2026-08-07T21:00:00+00:00",
            episode_id="episode-1",
            operation=Operation.MATERIALIZE,
            standing=Standing.ALIVE,
        )
    )
    ledger.append(
        Receipt(
            receipt_id="receipt-2",
            occurred_at="2026-08-07T21:00:01+00:00",
            episode_id="episode-1",
            operation=Operation.VERIFY,
            standing=Standing.ALIVE,
            verification_id="verification-1",
        )
    )
    return ledger.records()


def test_checkpoint_authenticates_the_complete_chain_prefix() -> None:
    records = _records()
    key = HmacSha256CheckpointKey(key_id="kms://acme/audit-key/7", secret=b"k" * 32)

    checkpoint = create_evidence_checkpoint(records, key)

    assert checkpoint.version == CHECKPOINT_VERSION
    assert checkpoint.record_count == 2
    assert checkpoint.chain_tip == records[-1].record_digest
    assert checkpoint.algorithm == "HMAC-SHA256"
    assert checkpoint.key_id == "kms://acme/audit-key/7"
    assert verify_evidence_checkpoint(records, checkpoint, key) is True


def test_checkpoint_rejects_tampered_chain_tip_and_wrong_key() -> None:
    records = _records()
    key = HmacSha256CheckpointKey(key_id="audit-key", secret=b"a" * 32)
    wrong_key = HmacSha256CheckpointKey(key_id="audit-key", secret=b"b" * 32)
    checkpoint = create_evidence_checkpoint(records, key)

    tampered = checkpoint.model_copy(update={"chain_tip": "0" * 64})

    assert verify_evidence_checkpoint(records, tampered, key) is False
    assert verify_evidence_checkpoint(records, checkpoint, wrong_key) is False


def test_checkpoint_rejects_record_mutation_even_with_original_authenticator() -> None:
    records = _records()
    key = HmacSha256CheckpointKey(key_id="audit-key", secret=b"a" * 32)
    checkpoint = create_evidence_checkpoint(records, key)
    mutated = (
        records[0],
        records[1].model_copy(update={"record_digest": "f" * 64}),
    )

    assert verify_evidence_checkpoint(mutated, checkpoint, key) is False


def test_checkpoint_payload_is_deterministic_and_binds_verifier_identity() -> None:
    payload = checkpoint_payload(
        record_count=2,
        chain_tip="abc",
        algorithm="KMS-ALGORITHM",
        key_id="kms://key/42",
    )
    assert payload == checkpoint_payload(
        key_id="kms://key/42",
        algorithm="KMS-ALGORITHM",
        chain_tip="abc",
        record_count=2,
    )
    assert b'"key_id":"kms://key/42"' in payload
    assert b'"algorithm":"KMS-ALGORITHM"' in payload


def test_hmac_reference_key_requires_enterprise_sized_secret_and_named_key() -> None:
    with pytest.raises(ValueError, match="CHECKPOINT_HMAC_KEY_TOO_SHORT"):
        HmacSha256CheckpointKey(key_id="audit-key", secret=b"short")
    with pytest.raises(ValueError, match="EMPTY_CHECKPOINT_KEY_ID"):
        HmacSha256CheckpointKey(key_id=" ", secret=b"k" * 32)
