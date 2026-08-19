from __future__ import annotations

from blake3 import blake3
import json

from gymact.gyms.gcp_empirical import (
    EmpiricalProbeReceipt,
    admit_empirical_probe_receipts,
    parse_empirical_probe_receipt,
)


def _receipt(method_id: str = "compute:v1:instances.get") -> EmpiricalProbeReceipt:
    payload = {
        "subject": "gcp://project/example",
        "method_id": method_id,
        "request_digest_blake3": "a" * 64,
        "response_digest_blake3": "b" * 64,
        "projection_digest_blake3": "c" * 64,
        "observed_at": "2026-08-19T15:00:00Z",
        "executor": "brce:gcp-live-probe",
    }
    digest = blake3(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return EmpiricalProbeReceipt(**payload, receipt_digest_blake3=digest)


def test_empirical_receipt_is_admitted_only_with_integrity() -> None:
    receipt = _receipt()
    assert receipt.valid
    observation = admit_empirical_probe_receipts((receipt,))
    assert observation.admitted
    assert observation.receipt is not None
    assert observation.artifacts[0].identity == receipt.method_id


def test_empty_empirical_evidence_is_blocked() -> None:
    observation = admit_empirical_probe_receipts(())
    assert observation.disposition == "BLOCKED"
    assert observation.reason == "NO_EMPIRICAL_PROBE_RECEIPTS"


def test_duplicate_empirical_method_is_refused() -> None:
    receipt = _receipt()
    observation = admit_empirical_probe_receipts((receipt, receipt))
    assert observation.disposition == "REFUSED"
    assert observation.reason == "DUPLICATE_EMPIRICAL_METHOD_RECEIPTS:compute:v1:instances.get"


def test_tampered_empirical_receipt_is_refused_at_parse_boundary() -> None:
    receipt = _receipt()
    value = receipt.payload | {"receipt_digest_blake3": "0" * 64}
    try:
        parse_empirical_probe_receipt(value)
    except ValueError as exc:
        assert str(exc).startswith("EMPIRICAL_RECEIPT_DIGEST_MISMATCH:")
    else:
        raise AssertionError("tampered empirical receipt was admitted")
