from dataclasses import dataclass


@dataclass(frozen=True)
class Contradiction:
    key: str
    values: tuple[object, ...]


def detect(observations: tuple[dict, ...], field: str) -> Contradiction | None:
    values = tuple(sorted({repr(item[field]) for item in observations if field in item}))
    return Contradiction(field, values) if len(values) > 1 else None
