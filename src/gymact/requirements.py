"""Machine-checkable Crown requirements and GALL checkpoint inventory."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

RequirementStatus = Literal["SATISFIED", "PARTIAL", "MISSING", "BLOCKED"]
SCHEMA_PATH = Path(__file__).with_name("schemas") / "crown-v26.8.7.json"


class RequirementsError(ValueError):
    """Raised when the packaged Crown requirements lose structural integrity."""


@dataclass(frozen=True)
class CrownSummary:
    specification: str
    requirements: int
    checkpoints: int
    requirement_statuses: dict[str, int]
    checkpoint_statuses: dict[str, int]
    crown_ready: bool
    blockers: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "specification": self.specification,
            "requirements": self.requirements,
            "checkpoints": self.checkpoints,
            "requirement_statuses": self.requirement_statuses,
            "checkpoint_statuses": self.checkpoint_statuses,
            "crown_ready": self.crown_ready,
            "blockers": list(self.blockers),
        }


def load_crown_requirements(path: Path | None = None) -> dict[str, Any]:
    target = path or SCHEMA_PATH
    data = json.loads(target.read_text(encoding="utf-8"))
    validate_crown_requirements(data)
    return data


def validate_crown_requirements(data: dict[str, Any]) -> None:
    statuses = tuple(data.get("statuses", ()))
    if statuses != ("SATISFIED", "PARTIAL", "MISSING", "BLOCKED"):
        raise RequirementsError("INVALID_REQUIREMENT_STATUS_VOCABULARY")

    ladder = tuple(data.get("standing_ladder", ()))
    if ladder != (
        "UNKNOWN",
        "CANDIDATE",
        "STRUCTURAL",
        "PARTIAL_ALIVE",
        "ALIVE",
        "ADOPTED",
    ):
        raise RequirementsError("INVALID_STANDING_LADDER")

    requirements = data.get("requirements")
    if not isinstance(requirements, dict) or not requirements:
        raise RequirementsError("REQUIREMENTS_MISSING")
    for requirement_id, requirement in requirements.items():
        if not requirement_id.startswith("G-"):
            raise RequirementsError(f"INVALID_REQUIREMENT_ID:{requirement_id}")
        if requirement.get("status") not in statuses:
            raise RequirementsError(f"INVALID_REQUIREMENT_STATUS:{requirement_id}")
        if requirement.get("priority") not in {"LAW", "P0", "P1", "P2"}:
            raise RequirementsError(f"INVALID_REQUIREMENT_PRIORITY:{requirement_id}")
        if not isinstance(requirement.get("evidence"), list):
            raise RequirementsError(f"INVALID_EVIDENCE_LIST:{requirement_id}")

    checkpoints = data.get("gall_checkpoints")
    expected = [f"CP{i}" for i in range(17)]
    if not isinstance(checkpoints, dict) or list(checkpoints) != expected:
        raise RequirementsError("GALL_CHECKPOINT_SEQUENCE_BROKEN")
    for checkpoint_id, checkpoint in checkpoints.items():
        if checkpoint.get("status") not in statuses:
            raise RequirementsError(f"INVALID_CHECKPOINT_STATUS:{checkpoint_id}")

    crown = data.get("crown", {})
    if crown.get("requires") != expected:
        raise RequirementsError("CROWN_CHECKPOINT_CLOSURE_BROKEN")
    if crown.get("incorrect_safety_crowns_max") != 0:
        raise RequirementsError("SAFETY_CROWN_BUDGET_MUST_BE_ZERO")


def crown_summary(data: dict[str, Any] | None = None) -> CrownSummary:
    inventory = data or load_crown_requirements()
    validate_crown_requirements(inventory)
    requirements = inventory["requirements"]
    checkpoints = inventory["gall_checkpoints"]
    req_counts = Counter(item["status"] for item in requirements.values())
    cp_counts = Counter(item["status"] for item in checkpoints.values())
    blockers = tuple(
        checkpoint_id
        for checkpoint_id in inventory["crown"]["requires"]
        if checkpoints[checkpoint_id]["status"] != "SATISFIED"
    )
    return CrownSummary(
        specification=inventory["spec_version"],
        requirements=len(requirements),
        checkpoints=len(checkpoints),
        requirement_statuses={status: req_counts.get(status, 0) for status in inventory["statuses"]},
        checkpoint_statuses={status: cp_counts.get(status, 0) for status in inventory["statuses"]},
        crown_ready=not blockers,
        blockers=blockers,
    )
