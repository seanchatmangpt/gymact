from __future__ import annotations

from dataclasses import dataclass

from .subject import Subject


@dataclass(frozen=True, slots=True)
class Movement:
    before: Subject
    after: Subject
    kind: str

    def __post_init__(self) -> None:
        if self.before.repo != self.after.repo:
            raise ValueError("REFUSED_CROSS_REPOSITORY_MOVEMENT")
        if self.before.sha == self.after.sha:
            raise ValueError("REFUSED_ZERO_MOVEMENT")
        if self.kind not in {"BRANCH", "PR_HEAD", "DEFAULT_HEAD"}:
            raise ValueError("REFUSED_UNKNOWN_MOVEMENT_KIND")

    @property
    def changed(self) -> bool:
        return True
