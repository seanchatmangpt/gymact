from dataclasses import dataclass


@dataclass(frozen=True)
class Contradiction:
    key: str
    outcomes: tuple[str, ...]


def detect(rows: list[tuple[str, str]]) -> tuple[Contradiction, ...]:
    by_key = {}
    for key, outcome in rows:
        by_key.setdefault(key, set()).add(outcome)
    return tuple(
        Contradiction(key, tuple(sorted(outcomes)))
        for key, outcomes in sorted(by_key.items())
        if len(outcomes) > 1
    )
