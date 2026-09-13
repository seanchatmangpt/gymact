"""Evidence replay admission. Replay validates evidence and never silently actuates."""
from __future__ import annotations

from enum import StrEnum
from typing import Any, Protocol

from pydantic import Field

from gymact.models import FrozenModel


class ReplayMode(StrEnum):
    EVIDENCE_REPLAY = "EVIDENCE_REPLAY"
    VERIFIER_REPLAY = "VERIFIER_REPLAY"
    SIMULATION_REPLAY = "SIMULATION_REPLAY"
    LIVE_REEXECUTION = "LIVE_REEXECUTION"


class ReplayExpectation(FrozenModel):
    subject_ref: str | None = None
    capability_ref: str | None = None
    policy_revision: str | None = None
    principal: str | None = None
    possibility_graph_digest: str | None = None
    possibility_exploration_digest: str | None = None
    possibility_path_id: str | None = None
    possibility_morphism_id: str | None = None
    selection_digest: str | None = None


class ReplayReport(FrozenModel):
    mode: ReplayMode
    valid: bool
    record_count: int = Field(default=0, ge=0)
    head_digest: str | None = None
    mismatches: tuple[str, ...] = ()
    live_reexecution_admitted: bool = False


class LedgerLike(Protocol):
    def verify(self) -> bool: ...
    def records(self) -> tuple[Any, ...]: ...


_LEGACY_OPTIONAL_IDENTITY_FIELDS = (
    "subject_ref",
    "capability_ref",
    "policy_revision",
    "principal",
)
_DCM_STRICT_IDENTITY_FIELDS = (
    "possibility_graph_digest",
    "possibility_exploration_digest",
    "possibility_path_id",
    "possibility_morphism_id",
    "selection_digest",
)


def _identity_mismatches(receipt: Any, expected: ReplayExpectation) -> list[str]:
    mismatches: list[str] = []
    for field in _LEGACY_OPTIONAL_IDENTITY_FIELDS:
        wanted = getattr(expected, field)
        actual = getattr(receipt, field, None)
        if wanted is not None and actual not in {None, wanted}:
            mismatches.append(f"{field.upper()}_DRIFT")
    for field in _DCM_STRICT_IDENTITY_FIELDS:
        wanted = getattr(expected, field)
        actual = getattr(receipt, field, None)
        if wanted is not None and actual != wanted:
            suffix = "MISSING" if actual is None else "DRIFT"
            mismatches.append(f"{field.upper()}_{suffix}")
    return mismatches


def replay_ledger(
    ledger: LedgerLike,
    *,
    mode: ReplayMode = ReplayMode.EVIDENCE_REPLAY,
    expected: ReplayExpectation | None = None,
    allow_live_reexecution: bool = False,
) -> ReplayReport:
    """Verify chain, causal parent closure, and optional admitted identity.

    Even when LIVE_REEXECUTION is explicitly admitted this function only reports
    admission. It has no executor parameter and therefore cannot actuate.
    """
    if mode is ReplayMode.LIVE_REEXECUTION and not allow_live_reexecution:
        return ReplayReport(
            mode=mode,
            valid=False,
            mismatches=("LIVE_REEXECUTION_REFUSED",),
        )

    records = tuple(ledger.records())
    if not ledger.verify():
        return ReplayReport(
            mode=mode,
            valid=False,
            record_count=len(records),
            head_digest=getattr(records[-1], "record_digest", None) if records else None,
            mismatches=("EVIDENCE_CHAIN_INVALID",),
            live_reexecution_admitted=(
                mode is ReplayMode.LIVE_REEXECUTION and allow_live_reexecution
            ),
        )

    seen: set[str] = set()
    mismatches: list[str] = []
    for record in records:
        receipt = record.receipt
        for parent in getattr(receipt, "parent_receipt_ids", ()):
            if parent not in seen:
                mismatches.append(f"PARENT_RECEIPT_MISSING_OR_FORWARD:{parent}")
        if expected is not None:
            mismatches.extend(_identity_mismatches(receipt, expected))
        receipt_id = getattr(receipt, "receipt_id", None)
        if receipt_id:
            seen.add(receipt_id)

    return ReplayReport(
        mode=mode,
        valid=not mismatches,
        record_count=len(records),
        head_digest=getattr(records[-1], "record_digest", None) if records else None,
        mismatches=tuple(mismatches),
        live_reexecution_admitted=(
            mode is ReplayMode.LIVE_REEXECUTION and allow_live_reexecution and not mismatches
        ),
    )
