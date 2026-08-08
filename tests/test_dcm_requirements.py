from __future__ import annotations

import copy

import pytest

from gymact.dcm_requirements import (
    dcm_requirements_summary,
    load_dcm_requirements,
    validate_dcm_requirements,
)


def test_packaged_dcm_laws_are_complete_but_not_false_crowned() -> None:
    data = load_dcm_requirements()
    assert [item["id"] for item in data["requirements"]] == [
        f"DCM-{index:03d}" for index in range(1, 19)
    ]
    summary = dcm_requirements_summary()
    assert summary.total == 18
    assert summary.witnessed_crown is False
    assert summary.standings["STRUCTURAL"] == 17
    assert summary.standings["UNKNOWN"] == 1


def test_mutated_crown_cannot_predeclare_alive() -> None:
    data = copy.deepcopy(load_dcm_requirements())
    data["requirements"][-1]["standing"] = "ALIVE"
    with pytest.raises(ValueError, match="DCM_CROWN_CANNOT_BE_PREMARKED_ALIVE"):
        validate_dcm_requirements(data)
