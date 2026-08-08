"""Machine-checkable 80/20 ERRC innovation ledger for GymAct v26.8.7."""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

ERRC_PATH = Path(__file__).with_name("schemas") / "errc-v26.8.7.json"


class ERRCMove(StrEnum):
    ELIMINATE = "ELIMINATE"
    REDUCE = "REDUCE"
    RAISE = "RAISE"
    CREATE = "CREATE"


class ERRCStatus(StrEnum):
    SATISFIED = "SATISFIED"
    PARTIAL = "PARTIAL"
    BLOCKED = "BLOCKED"


class ERRCItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    item_id: str = Field(min_length=1)
    move: ERRCMove
    outcome: str = Field(min_length=1)
    requirement_refs: tuple[str, ...]
    evidence: tuple[str, ...]
    impact: int = Field(ge=1, le=5)
    effort: int = Field(ge=1, le=5)
    status: ERRCStatus

    @property
    def leverage(self) -> float:
        return self.impact / self.effort


@dataclass(frozen=True)
class ERRCSummary:
    items: int
    statuses: dict[str, int]
    moves: dict[str, int]
    high_leverage: tuple[str, ...]
    complete: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "items": self.items,
            "statuses": self.statuses,
            "moves": self.moves,
            "high_leverage": list(self.high_leverage),
            "complete": self.complete,
        }


def load_errc(path: Path | None = None) -> tuple[ERRCItem, ...]:
    target = path or ERRC_PATH
    raw = json.loads(target.read_text(encoding="utf-8"))
    items = tuple(ERRCItem.model_validate(item) for item in raw.get("items", ()))
    if not items:
        raise ValueError("ERRC_ITEMS_REQUIRED")
    if len({item.item_id for item in items}) != len(items):
        raise ValueError("ERRC_ITEM_IDS_MUST_BE_UNIQUE")
    for item in items:
        if not item.requirement_refs:
            raise ValueError(f"ERRC_REQUIREMENT_TRACE_REQUIRED:{item.item_id}")
        if not item.evidence:
            raise ValueError(f"ERRC_EVIDENCE_REQUIRED:{item.item_id}")
    return items


def errc_summary(items: tuple[ERRCItem, ...] | None = None) -> ERRCSummary:
    values = items or load_errc()
    statuses = Counter(item.status.value for item in values)
    moves = Counter(item.move.value for item in values)
    ranked = tuple(
        item.item_id
        for item in sorted(values, key=lambda item: (-item.leverage, item.item_id))
        if item.leverage >= 2.0
    )
    return ERRCSummary(
        items=len(values),
        statuses=dict(statuses),
        moves=dict(moves),
        high_leverage=ranked,
        complete=all(item.status is ERRCStatus.SATISFIED for item in values),
    )
