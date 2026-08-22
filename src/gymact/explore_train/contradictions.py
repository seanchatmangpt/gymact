from dataclasses import dataclass

@dataclass(frozen=True)
class Contradiction:
    key: str
    values: tuple[object, ...]


def detect(observations: tuple[dict, ...], field: str) -> Contradiction | None:
    values = tuple(sorted({repr(o[field]) for o in observations if field in o}))
    return Contradiction(field, values) if len(values) > 1 else None
