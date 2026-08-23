from __future__ import annotations

from dataclasses import dataclass

from .identity import Refused, Subject


@dataclass(frozen=True, slots=True)
class RuntimeReceipt:
    subject: Subject
    topology: str
    transport: str
    encrypted: bool
    exit_status: int


def admit_runtime_receipt(receipt: RuntimeReceipt, *, require_tls: bool = False) -> RuntimeReceipt:
    if receipt.exit_status != 0:
        raise Refused("REFUSED_RUNTIME_EXIT_FAILURE")
    if require_tls and (receipt.transport != "inet_tls" or not receipt.encrypted):
        raise Refused("REFUSED_TLS_RECEIPT_TRANSPORT_CONTRADICTION")
    if "tls" in receipt.topology.lower() and (receipt.transport != "inet_tls" or not receipt.encrypted):
        raise Refused("REFUSED_TLS_RECEIPT_TRANSPORT_CONTRADICTION")
    return receipt
