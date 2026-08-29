from __future__ import annotations

from dataclasses import dataclass

from .refusal import Refused


@dataclass(frozen=True, order=True)
class Event:
    activity: str
    object_id: str
    lifecycle: str = "complete"

    def __post_init__(self) -> None:
        if not self.activity.strip() or not self.object_id.strip():
            raise Refused("INVALID_EVENT_IDENTITY")
        if self.lifecycle not in {"start", "complete", "suspend", "resume"}:
            raise Refused("INVALID_LIFECYCLE", self.lifecycle)

    @property
    def semantic_key(self) -> tuple[str, str, str]:
        return (self.activity, self.object_id, self.lifecycle)
