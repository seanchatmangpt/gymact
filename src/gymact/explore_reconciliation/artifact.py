from __future__ import annotations

import re
from dataclasses import dataclass

_HEX64 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class Artifact:
    name: str
    sha256: str
    producer_run_id: int
    subject_sha: str

    def __post_init__(self) -> None:
        if not self.name.strip() or not _HEX64.fullmatch(self.sha256):
            raise ValueError("REFUSED_INVALID_ARTIFACT_IDENTITY")
        if self.producer_run_id <= 0 or len(self.subject_sha) != 40:
            raise ValueError("REFUSED_UNBOUND_ARTIFACT")

    def belongs_to(self, subject_sha: str) -> bool:
        return self.subject_sha == subject_sha
