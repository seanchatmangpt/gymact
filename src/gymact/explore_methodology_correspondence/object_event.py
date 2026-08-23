from dataclasses import dataclass

@dataclass(frozen=True)
class Event:
    event_id: str
    activity: str
    object_ids: frozenset[str]


def project_object_centric(events: tuple[Event, ...], object_id: str) -> tuple[Event, ...]:
    return tuple(e for e in events if object_id in e.object_ids)


def project_event_centric(events: tuple[Event, ...]) -> tuple[str, ...]:
    return tuple(e.activity for e in events)
