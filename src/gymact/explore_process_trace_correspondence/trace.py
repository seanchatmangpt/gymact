from __future__ import annotations

from dataclasses import dataclass

from .event import Event
from .refusal import Refused
from .subject import Subject


@dataclass(frozen=True)
class Trace:
    subject: Subject
    engine: str
    events: tuple[Event, ...]

    def __post_init__(self) -> None:
        if not self.engine.strip():
            raise Refused("MISSING_ENGINE_IDENTITY")
        if not self.events:
            raise Refused("EMPTY_TRACE")

    def keys(self) -> tuple[tuple[str, str, str], ...]:
        return tuple(event.semantic_key for event in self.events)
