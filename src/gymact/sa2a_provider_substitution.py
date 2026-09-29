"""Provider substitution cannot alter exact subject, receipt, replay, or authority."""
from __future__ import annotations
from gymact.sa2a_envelope import SA2AReplanEnvelope

def admit_substitution(original:SA2AReplanEnvelope,candidate:SA2AReplanEnvelope)->SA2AReplanEnvelope:
    if candidate.exact_subject != original.exact_subject: raise ValueError("SA2A_SUBSTITUTION_SUBJECT_DRIFT")
    if candidate.receipt_id != original.receipt_id: raise ValueError("SA2A_SUBSTITUTION_RECEIPT_DRIFT")
    if candidate.source_replay_key != original.source_replay_key: raise ValueError("SA2A_SUBSTITUTION_REPLAY_DRIFT")
    if candidate.decision.authority != "none": raise ValueError("SA2A_SUBSTITUTION_AUTHORITY_REFUSED")
    return candidate
