"""Powerless SA2A feedback projection for GymAct environment evolution."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, JsonValue

from gymact.consequence_binding import ConsequenceBinding
from gymact.evidence import digest
from gymact.models import FrozenModel
from gymact.sa2a_consumer import consume_sa2a_replan
from gymact.sa2a_envelope import SA2AReplanEnvelope, admit_envelope

_CONTENT_DIGEST = r"^blake3:[0-9a-f]{64}$"


class SA2AEvolutionFeedback(FrozenModel):
    exact_subject: JsonValue
    receipt_id: str = Field(min_length=1)
    envelope_digest: str = Field(pattern=_CONTENT_DIGEST)
    decision_kind: Literal["stop", "replan"]
    decision_reason: str = Field(min_length=1)
    source_replay_key: str | None = None
    authority: Literal["none"] = "none"


def evolution_feedback(
    value: SA2AReplanEnvelope | dict[str, object],
    *,
    binding: ConsequenceBinding | None = None,
) -> SA2AEvolutionFeedback:
    envelope = admit_envelope(value)
    directive = consume_sa2a_replan(envelope, binding=binding)

    return SA2AEvolutionFeedback(
        exact_subject=directive.exact_subject,
        receipt_id=directive.receipt_id,
        envelope_digest="blake3:" + digest(envelope.model_dump(mode="json")),
        decision_kind=directive.kind,
        decision_reason=directive.reason,
        source_replay_key=envelope.source_replay_key,
    )
