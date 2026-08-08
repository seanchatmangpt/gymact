from __future__ import annotations

import json

import pytest

from gymact.requirements import (
    RequirementsError,
    crown_summary,
    load_crown_requirements,
    validate_crown_requirements,
)


def test_packaged_inventory_is_closed_and_no_requirement_is_missing() -> None:
    data = load_crown_requirements()
    assert len(data["requirements"]) == 49
    assert list(data["gall_checkpoints"]) == [f"CP{i}" for i in range(17)]
    assert all(item["status"] != "MISSING" for item in data["requirements"].values())


def test_summary_refuses_false_crown_while_external_checkpoints_remain() -> None:
    summary = crown_summary()
    assert summary.crown_ready is False
    assert "CP0" in summary.blockers
    assert "CP11" in summary.blockers
    assert "CP14" in summary.blockers
    assert "CP16" in summary.blockers
    assert "CP3" not in summary.blockers
    assert summary.requirement_statuses["MISSING"] == 0
    assert summary.requirement_statuses["PARTIAL"] > 0


def test_mutated_safety_budget_is_rejected() -> None:
    data = json.loads(json.dumps(load_crown_requirements()))
    data["crown"]["incorrect_safety_crowns_max"] = 1
    with pytest.raises(RequirementsError, match="SAFETY_CROWN_BUDGET_MUST_BE_ZERO"):
        validate_crown_requirements(data)
