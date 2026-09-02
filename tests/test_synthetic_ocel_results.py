"""Synthetic OCEL results: indistinguishable operationally, explicit in audit."""

from __future__ import annotations

import pytest

from gymact.manufacture import synthetic_ocel_manufacturing_contract
from gymact.ocel import digest_ocel_log, validate_ocel_log
from gymact.synthetic_ocel import (
    OCELGymResult,
    OCELTraceOrigin,
    OCELTraceProvenance,
    manufacture_ocel_history,
    observed_ocel_result,
    operationally_equivalent,
)


def _history() -> dict:
    return {
        "eventTypes": [
            {
                "name": "PlanCreated",
                "attributes": [{"name": "status", "type": "string"}],
            }
        ],
        "objectTypes": [
            {"name": "planner", "attributes": []},
            {"name": "plan", "attributes": []},
        ],
        "events": [
            {
                "id": "event-1",
                "type": "PlanCreated",
                "time": "2026-09-02T21:00:00Z",
                "attributes": [{"name": "status", "value": "admitted"}],
                "relationships": [
                    {"objectId": "planner-a", "qualifier": "actor"},
                    {"objectId": "plan-1", "qualifier": "result"},
                ],
            }
        ],
        "objects": [
            {"id": "planner-a", "type": "planner", "attributes": []},
            {"id": "plan-1", "type": "plan", "attributes": []},
        ],
    }


def test_manufactured_history_is_real_ocel_but_never_execution_evidence() -> None:
    result = manufacture_ocel_history(
        history_spec=_history(),
        claimed_actor="PlannerA",
        generator_spec={"planner": "PlannerA", "objective": "min-latency"},
        world_model={"world": "calendar-v1"},
        seed=7,
    )

    validate_ocel_log(result.operational_view())
    audit = result.audit_view()

    assert audit["provenance"]["origin"] == "GGEN_MANUFACTURED"
    assert audit["provenance"]["observed_execution"] is False
    assert audit["provenance"]["manufactured_trace"] is True
    assert audit["provenance"]["claimed_actor"] == "PlannerA"
    assert audit["execution_receipt_refs"] == []


def test_operational_projection_can_be_identical_while_audit_remains_distinguishable() -> None:
    history = _history()
    real = observed_ocel_result(
        history,
        source_ref="google-workspace:captured-trace",
        claimed_actor="PlannerA",
    )
    manufactured = manufacture_ocel_history(
        history_spec=history,
        claimed_actor="PlannerA",
        generator_spec={"planner": "PlannerA"},
        world_model={"world": "calendar-v1"},
        seed=9,
    )

    assert operationally_equivalent(real, manufactured)
    assert real.operational_view() == manufactured.operational_view()
    assert real.audit_view()["provenance"]["origin"] == "REAL_OBSERVED"
    assert manufactured.audit_view()["provenance"]["origin"] == "GGEN_MANUFACTURED"
    assert real.audit_view() != manufactured.audit_view()


def test_manufacture_is_deterministically_content_addressed() -> None:
    kwargs = {
        "history_spec": _history(),
        "claimed_actor": "PlannerA",
        "generator_spec": {"planner": "PlannerA", "temperature": 0},
        "world_model": {"world": "calendar-v1", "version": 3},
        "seed": "seed-42",
    }
    left = manufacture_ocel_history(**kwargs)
    right = manufacture_ocel_history(**kwargs)

    assert left.provenance == right.provenance
    assert left.provenance.trace_digest == digest_ocel_log(_history())
    assert left.audit_view() == right.audit_view()


def test_manufactured_provenance_refuses_false_execution_claim() -> None:
    with pytest.raises(ValueError, match="CANNOT_CLAIM_OBSERVED_EXECUTION"):
        OCELTraceProvenance(
            origin=OCELTraceOrigin.GGEN_MANUFACTURED,
            trace_digest=digest_ocel_log(_history()),
            observed_execution=True,
            manufactured_trace=True,
            claimed_actor="PlannerA",
            generator="ggen",
            generator_spec_digest="spec",
            world_model_digest="world",
            seed=1,
        )


def test_manufactured_result_refuses_execution_receipt() -> None:
    manufactured = manufacture_ocel_history(
        history_spec=_history(),
        claimed_actor="PlannerA",
        generator_spec={"planner": "PlannerA"},
        world_model={"world": "calendar-v1"},
        seed=1,
    )

    with pytest.raises(ValueError, match="CANNOT_CARRY_EXECUTION_RECEIPT"):
        OCELGymResult(
            log=manufactured.log,
            provenance=manufactured.provenance,
            execution_receipt_refs=("receipt-that-never-ran",),
        )


def test_ggen_contract_makes_the_evidence_fence_machine_readable() -> None:
    contract = synthetic_ocel_manufacturing_contract()

    assert contract["canonical_result"] == "OCEL_2_0"
    assert contract["operational_projection"] == "ocel_only"
    assert contract["audit_projection"] == "ocel_plus_provenance"
    assert "execution_receipt" in contract["forbidden"]
    assert "observed_execution=true" in contract["forbidden"]
