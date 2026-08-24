from dataclasses import dataclass

from .refusal import FederationRefusal


@dataclass(frozen=True)
class ObjectEvent:
    event_id: str
    activity: str
    object_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.event_id or not self.activity or not self.object_ids:
            raise FederationRefusal("INVALID_OBJECT_EVENT")
        if len(set(self.object_ids)) != len(self.object_ids):
            raise FederationRefusal("DUPLICATE_OBJECT_REFERENCE")


def object_lifecycle(events: tuple[ObjectEvent, ...], object_id: str) -> tuple[str, ...]:
    lifecycle = tuple(e.activity for e in events if object_id in e.object_ids)
    if not lifecycle:
        raise FederationRefusal("OBJECT_NOT_OBSERVED")
    return lifecycle
