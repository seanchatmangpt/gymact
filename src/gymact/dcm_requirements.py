"""Machine-checkable Design for Combinatorial Maximum requirements."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import Field

from gymact.models import FrozenModel, Standing

_SCHEMA_PATH = Path(__file__).with_name("schemas") / "dcm-v26.8.7.json"
_EXPECTED_IDS = tuple(f"DCM-{index:03d}" for index in range(1, 19))
_ALLOWED_STANDINGS = {
    Standing.UNKNOWN.value,
    Standing.CANDIDATE.value,
    Standing.STRUCTURAL.value,
    Standing.PARTIAL_ALIVE.value,
    Standing.ALIVE.value,
    Standing.ADOPTED.value,
    Standing.BLOCKED.value,
    Standing.UNSUPPORTED.value,
    Standing.REFUSED.value,
    Standing.STALE.value,
}


class DCMRequirementsSummary(FrozenModel):
    total: int = Field(ge=0)
    standings: dict[str, int]
    witnessed_crown: bool


def load_dcm_requirements(path: Path | None = None) -> dict[str, Any]:
    target = path or _SCHEMA_PATH
    data = json.loads(target.read_text(encoding="utf-8"))
    validate_dcm_requirements(data)
    return data


def validate_dcm_requirements(data: dict[str, Any]) -> None:
    if data.get("spec_version") != "26.8.7":
        raise ValueError("DCM_SPEC_VERSION_MISMATCH")
    requirements = data.get("requirements")
    if not isinstance(requirements, list):
        raise ValueError("DCM_REQUIREMENTS_MUST_BE_LIST")
    ids = tuple(item.get("id") for item in requirements)
    if ids != _EXPECTED_IDS:
        raise ValueError("DCM_REQUIREMENT_ID_SET_MISMATCH")
    if len(ids) != len(set(ids)):
        raise ValueError("DCM_DUPLICATE_REQUIREMENT_ID")
    for item in requirements:
        standing = item.get("standing")
        if standing not in _ALLOWED_STANDINGS:
            raise ValueError(f"DCM_STANDING_INVALID:{item.get('id')}")
        implementation = item.get("implementation")
        if not isinstance(implementation, list) or not implementation:
            raise ValueError(f"DCM_IMPLEMENTATION_EVIDENCE_REQUIRED:{item.get('id')}")
    crown = requirements[-1]
    if crown["id"] != "DCM-018":
        raise ValueError("DCM_CROWN_REQUIREMENT_MISSING")
    if crown["standing"] in {Standing.ALIVE.value, Standing.ADOPTED.value}:
        raise ValueError("DCM_CROWN_CANNOT_BE_PREMARKED_ALIVE")


def dcm_requirements_summary() -> DCMRequirementsSummary:
    data = load_dcm_requirements()
    standings: dict[str, int] = {}
    for item in data["requirements"]:
        value = str(item["standing"])
        standings[value] = standings.get(value, 0) + 1
    return DCMRequirementsSummary(
        total=len(data["requirements"]),
        standings=standings,
        witnessed_crown=standings.get(Standing.ALIVE.value, 0) == len(data["requirements"]),
    )
