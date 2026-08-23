from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

CIConclusion = Literal["success", "failure", "cancelled", "skipped", "pending", "unknown"]


@dataclass(frozen=True, slots=True)
class CIRun:
    run_id: int
    name: str
    conclusion: CIConclusion
    subject_sha: str

    def __post_init__(self) -> None:
        if self.run_id <= 0 or not self.name.strip():
            raise ValueError("REFUSED_INVALID_CI_IDENTITY")
        if len(self.subject_sha) != 40:
            raise ValueError("REFUSED_INEXACT_CI_SUBJECT")

    @property
    def evidence_outcome(self) -> str:
        return {"success": "PASS", "failure": "FAIL", "pending": "PENDING"}.get(
            self.conclusion, "UNKNOWN"
        )
