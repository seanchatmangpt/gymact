"""OCEL projection of portable SA2A provider outcomes."""
from __future__ import annotations
from typing import Any
from gymact.sa2a_envelope import SA2AReplanEnvelope

def project_sa2a_ocel(envelope: SA2AReplanEnvelope) -> dict[str,Any]:
    return {"event_type":"sa2a.provider.outcome","exact_subject":envelope.exact_subject,"receipt_id":envelope.receipt_id,"replay_key":envelope.source_replay_key,"consequence":envelope.consequence,"authority":"none"}
