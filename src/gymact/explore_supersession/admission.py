from __future__ import annotations

from collections import defaultdict

from .evidence import Evidence
from .subject import Refusal, Subject


def admit(subject: Subject, evidence: list[Evidence]) -> tuple[Evidence, ...]:
    by_key: dict[tuple[str, str, str, object], set[object]] = defaultdict(set)
    admitted: list[Evidence] = []
    for row in evidence:
        if row.subject.repo != subject.repo:
            raise Refusal("REFUSED_FOREIGN_REPOSITORY_EVIDENCE")
        key = (*row.key(), row.epoch)
        by_key[key].add(row.outcome)
        if len(by_key[key]) > 1:
            raise Refusal("REFUSED_CONTRADICTORY_EVIDENCE")
        admitted.append(row)
    return tuple(sorted(admitted, key=lambda item: (item.epoch, item.key())))
