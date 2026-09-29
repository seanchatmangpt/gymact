"""Unknown outcome is reconciled; it is never blindly retried."""
from __future__ import annotations
from gymact.sa2a_envelope import SA2ARecoveryDirective, SA2AReplanEnvelope
from gymact.sa2a_consumer import consume_sa2a_replan

def reconcile_outcome(envelope: SA2AReplanEnvelope) -> SA2ARecoveryDirective:
    directive=consume_sa2a_replan(envelope)
    if envelope.consequence=="unknown_outcome":
        return directive.model_copy(update={"kind":"replan","reason":"unknown_outcome_requires_reconciliation","authority":"none"})
    return directive
