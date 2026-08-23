from __future__ import annotations

from dataclasses import replace

from .evidence import Evidence, Outcome


def inject_failure(row: Evidence, *, outcome: Outcome = Outcome.FAIL) -> Evidence:
    return replace(row, outcome=outcome, evidence_id=f"{row.evidence_id}:injected")
