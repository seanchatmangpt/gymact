from __future__ import annotations

import json

import pytest

from gymact.requirements import (
    RequirementsError,
    crown_summary,
    load_crown_requirements,
    validate_crown_requirements,
)


def test_packaged_inventory_is_closed() -> None:
    data = load_crown_requirements()
    assert len(data["requirements"]) == 49
    assert list(data["gall_checkpoints"]) == [f"CP{i}" for i in range(17)]


def test_summary_refuses_false_crown() -> None:
    summary = crown_summary()
    assert summary.crown_ready is False
    assert "CP3" in summary.blockers
    assert summary.requirement_statuses["MISSING"] > 0


def test_mutated_safety_budget_is_rejected() -> None:
    data = json.loads(json.dumps(load_crown_requirements()))
    data["crown"]["incorrect_safety_crowns_max"] = 1
    with pytest.raises(RequirementsError, match="SAFETY_CROWN_BUDGET_MUST_BE_ZERO"):
        validate_crown_requirements(data)
