from dataclasses import dataclass


@dataclass(frozen=True)
class Delta:
    key: str
    before: object
    after: object
    changed: bool


def diff(before: dict, after: dict) -> tuple[Delta, ...]:
    keys = sorted(set(before) | set(after))
    return tuple(
        Delta(key, before.get(key), after.get(key), before.get(key) != after.get(key))
        for key in keys
    )
