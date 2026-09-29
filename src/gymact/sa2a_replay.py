"""Replay identity imported from the SA2A portable envelope."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, JsonValue

from gymact.models import FrozenModel
from gymact.sa2a_envelope import SA2AReplanEnvelope, admit_envelope


class SA2AReplayBinding(FrozenModel):
    exact_subject: JsonValue
    receipt_id: str = Field(min_length=1)
    source_replay_key: str = Field(min_length=1)
    authority: Literal["none"] = "none"


def bind_sa2a_replay(
    value: SA2AReplanEnvelope | dict[str, object],
) -> SA2AReplayBinding:
    envelope = admit_envelope(value)
    if not envelope.source_replay_key:
        raise ValueError("SA2A_SOURCE_REPLAY_KEY_REQUIRED")

    return SA2AReplayBinding(
        exact_subject=envelope.exact_subject,
        receipt_id=envelope.receipt_id,
        source_replay_key=envelope.source_replay_key,
    )
