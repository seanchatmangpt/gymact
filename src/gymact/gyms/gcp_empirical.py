"""Empirical GCP observation admission.

Static contracts describe possible externally observable behavior; they do not
prove execution. This module admits only concrete, externally produced probe
receipts whose subject, request, response, projection, and integrity digest are
all present. The resulting source observation closes the empirical source-family
rail without granting authority to perform probes itself.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Iterable, Mapping

from blake3 import blake3

from gymact.gyms.gcp_sources import (
    ContractArtifact,
    ContractSourceFamily,
    ContractSourceObservation,
)

__all__ = [
    "EmpiricalProbeReceipt",
    "admit_empirical_probe_receipts",
    "parse_empirical_probe_receipt",
]


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


@dataclass(frozen=True, slots=True)
class EmpiricalProbeReceipt:
    subject: str
    method_id: str
    request_digest_blake3: str
    response_digest_blake3: str
    projection_digest_blake3: str
    observed_at: str
    executor: str
    receipt_digest_blake3: str

    @property
    def payload(self) -> dict[str, str]:
        return {
            "subject": self.subject,
            "method_id": self.method_id,
            "request_digest_blake3": self.request_digest_blake3,
            "response_digest_blake3": self.response_digest_blake3,
            "projection_digest_blake3": self.projection_digest_blake3,
            "observed_at": self.observed_at,
            "executor": self.executor,
        }

    @property
    def valid(self) -> bool:
        if not all(self.payload.values()):
            return False
        expected = blake3(_canonical_json(self.payload).encode()).hexdigest()
        return self.receipt_digest_blake3 == expected


def parse_empirical_probe_receipt(value: Mapping[str, Any]) -> EmpiricalProbeReceipt:
    required = (
        "subject",
        "method_id",
        "request_digest_blake3",
        "response_digest_blake3",
        "projection_digest_blake3",
        "observed_at",
        "executor",
        "receipt_digest_blake3",
    )
    missing = [key for key in required if not isinstance(value.get(key), str) or not value.get(key)]
    if missing:
        raise ValueError(f"EMPIRICAL_RECEIPT_FIELDS_MISSING:{','.join(missing)}")
    receipt = EmpiricalProbeReceipt(**{key: str(value[key]) for key in required})
    if not receipt.valid:
        raise ValueError(f"EMPIRICAL_RECEIPT_DIGEST_MISMATCH:{receipt.method_id}")
    return receipt


def admit_empirical_probe_receipts(
    receipts: Iterable[EmpiricalProbeReceipt],
) -> ContractSourceObservation:
    items = tuple(receipts)
    if not items:
        return ContractSourceObservation(
            family=ContractSourceFamily.EMPIRICAL_OBSERVATION,
            disposition="BLOCKED",
            artifacts=(),
            receipt=None,
            reason="NO_EMPIRICAL_PROBE_RECEIPTS",
        )
    invalid = tuple(sorted(item.method_id for item in items if not item.valid))
    if invalid:
        return ContractSourceObservation(
            family=ContractSourceFamily.EMPIRICAL_OBSERVATION,
            disposition="REFUSED",
            artifacts=(),
            receipt=None,
            reason=f"INVALID_EMPIRICAL_RECEIPTS:{','.join(invalid)}",
        )
    identities = [item.method_id for item in items]
    duplicates = tuple(sorted({item for item in identities if identities.count(item) > 1}))
    if duplicates:
        return ContractSourceObservation(
            family=ContractSourceFamily.EMPIRICAL_OBSERVATION,
            disposition="REFUSED",
            artifacts=(),
            receipt=None,
            reason=f"DUPLICATE_EMPIRICAL_METHOD_RECEIPTS:{','.join(duplicates)}",
        )

    ordered = tuple(sorted(items, key=lambda item: item.method_id))
    artifacts = tuple(
        ContractArtifact(
            family=ContractSourceFamily.EMPIRICAL_OBSERVATION,
            identity=item.method_id,
            locator=item.subject,
            digest=item.receipt_digest_blake3,
            digest_algorithm="blake3-256",
            media_type="application/vnd.gymact.gcp-probe-receipt+json",
            metadata=(
                ("observed_at", item.observed_at),
                ("executor", item.executor),
                ("projection_digest_blake3", item.projection_digest_blake3),
            ),
        )
        for item in ordered
    )
    graph_payload = [item.payload | {"receipt_digest_blake3": item.receipt_digest_blake3} for item in ordered]
    digest = blake3(_canonical_json(graph_payload).encode()).hexdigest()
    return ContractSourceObservation(
        family=ContractSourceFamily.EMPIRICAL_OBSERVATION,
        disposition="ALIVE",
        artifacts=artifacts,
        receipt=f"gcp-empirical:blake3:{digest}",
        source_revision=digest,
    )
