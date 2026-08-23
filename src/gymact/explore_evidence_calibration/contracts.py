from __future__ import annotations

import re
from dataclasses import dataclass

_SHA = re.compile(r"^[0-9a-f]{40}$")
_REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


class Refusal(ValueError):
    """Typed fail-closed refusal."""


@dataclass(frozen=True)
class Subject:
    repo: str
    sha: str

    def __post_init__(self) -> None:
        if not _REPO.fullmatch(self.repo) or not _SHA.fullmatch(self.sha):
            raise Refusal("REFUSED_INEXACT_SUBJECT")

    @property
    def exact_id(self) -> str:
        return f"{self.repo}@{self.sha}"


OUTCOMES = frozenset({"PASS", "FAIL", "PENDING", "UNKNOWN", "UNSUPPORTED"})
STANDINGS = frozenset(
    {"UNKNOWN", "PARTIAL_ALIVE", "ALIVE", "BLOCKED", "BUILD_BROKEN", "UNSUPPORTED"}
)
