"""Powerless GymAct consumer for the portable SA2A replanning envelope."""

from __future__ import annotations

from gymact.consequence_binding import ConsequenceBinding
from gymact.sa2a_envelope import (
    SA2ARecoveryDirective,
    SA2AReplanEnvelope,
    admit_envelope,
)


def consume_sa2a_replan(
    value: SA2AReplanEnvelope | dict[str, object],
    *,
    binding: ConsequenceBinding | None = None,
) -> SA2ARecoveryDirective:
    """Consume the upstream decision without recreating consequence semantics."""
    envelope = admit_envelope(value)

    if binding is not None and binding.subject_ref != envelope.exact_subject:
        raise ValueError("SA2A_EXACT_SUBJECT_MISMATCH")

    return SA2ARecoveryDirective(
        exact_subject=envelope.exact_subject,
        receipt_id=envelope.receipt_id,
        consequence=envelope.consequence,
        kind=envelope.decision.kind,
        reason=envelope.decision.reason,
        authority=envelope.decision.authority,
        provider=envelope.provider,
    )
