"""Receipt feedback keeps receipt/replay identity exact and powerless."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from gymact.sa2a_envelope import SA2AReplanEnvelope
@dataclass(frozen=True)
class SA2AReceiptFeedback:
    receipt_id:str; replay_key:str|None; exact_subject:Any; authority:str="none"
def receipt_feedback(envelope:SA2AReplanEnvelope)->SA2AReceiptFeedback:
    return SA2AReceiptFeedback(envelope.receipt_id,envelope.source_replay_key,envelope.exact_subject)
