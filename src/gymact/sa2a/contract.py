"""Portable SA2A replan envelope admission. This module carries no actuation authority."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Literal

VERSION = "sa2a/replan-envelope/v1"
RecoveryDecision = Literal["retry", "reconcile", "refuse", "complete"]

@dataclass(frozen=True)
class ReplanEnvelope:
    subject: Any
    effect_id: str
    replay_identity: str
    outcome: str
    recovery: RecoveryDecision
    authority: Literal["none"] = "none"
    provider: str | None = None
    attempt: int | None = None

    @classmethod
    def from_wire(cls, value: dict[str, Any]) -> "ReplanEnvelope":
        if value.get("version") != VERSION or value.get("authority") != "none":
            raise ValueError("invalid portable SA2A envelope")
        recovery = value.get("recovery")
        if recovery not in {"retry", "reconcile", "refuse", "complete"}:
            raise ValueError("invalid recovery decision")
        return cls(subject=value["subject"], effect_id=str(value["effectId"]), replay_identity=str(value["replayIdentity"]), outcome=str(value["outcome"]), recovery=recovery, provider=value.get("provider"), attempt=value.get("attempt"))

    def to_wire(self) -> dict[str, Any]:
        return {"version": VERSION, "subject": self.subject, "effectId": self.effect_id, "replayIdentity": self.replay_identity, "outcome": self.outcome, "recovery": self.recovery, "authority": "none", "provider": self.provider, "attempt": self.attempt}
