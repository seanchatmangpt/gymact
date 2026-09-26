"""Redelivery / identity court for the ALOOP execution kernel (PR #148 round 3).

Attacks the residue left after the actuation-ledger repair (1143f94e):

* R01 a run that actuates and then typed-blocks must not actuate again when
  the same request is redelivered (exactly-once across redelivery).
* R02 a refusal AFTER an actuation (grant expires mid-run) carries the true
  count, and a redelivery with a renewed grant still does not re-execute.
* R03 a different request reusing the idempotency key of an unreconciled run
  is refused as a key conflict, not executed.
* R04 an unreconciled run of one work order does not block a different one.
* R05 result ledger views and receipts never alias: mutating one cannot
  rewrite receipt evidence (success path and dedupe replay).
* R06 zero-width / format / Unicode-space identity fields and empty or blank
  evidence requirements are refused at construction.

Collaborators are the court's real in-process fakes (``ScriptedProvider``,
``FakeVerifier``, virtual clock); assertions are on resulting state: the
provider's own execute counter and journal, LoopResult fields, receipts and
OCEL events.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from gymact.execution_loop import AuthorityGrant, ExecutionRequest, SubjectRef, loop_log
from gymact.ocel import validate_ocel_log


def _every_execute_moves(court: Any) -> Any:
    provider = court.ScriptedProvider(effect=court.ok_effect())
    cycle = {court.SHA_A: court.SHA_B, court.SHA_B: court.SHA_C, court.SHA_C: court.SHA_A}

    def move(p: Any) -> None:
        p.world["gymact"] = cycle[p.world["gymact"]]

    provider.on_execute = move
    return provider


def _events(result: Any, event_type: str) -> list[Any]:
    return [event for event in result.events if event.event_type == event_type]


def test_r01_redelivery_after_actuating_typed_block_does_not_actuate(court):
    provider = _every_execute_moves(court)
    loop, _ = court.make_loop([provider])
    request = court.make_request(resource_constraints=court.make_constraints(max_subject_moves=1))
    first = loop.run(request)
    assert first.outcome == "TypedBlock"
    assert first.typed_reason == "TYPED_BLOCK_MOVING_SUBJECT"
    assert first.actuation_count == provider.execute_calls == 2

    second = loop.run(request)
    assert provider.execute_calls == 2  # no new actuation
    assert len(provider.journal) == 2
    assert second.outcome == "TypedBlock"
    assert second.typed_reason == "TYPED_BLOCK_PRIOR_ACTUATION_UNRECONCILED"
    assert second.broken_term == "R_missing_consequence"
    assert second.actuation_count == 0
    assert second.actuations == []
    assert _events(second, "actuation") == []
    [block] = _events(second, "typed.block")
    assert block.attributes["prior_reason"] == "TYPED_BLOCK_MOVING_SUBJECT"
    assert block.attributes["prior_actuation_count"] == 2
    assert block.attributes["prior_provider_execution_ids"] == [
        entry["provider_execution_id"] for entry in first.actuations
    ]
    validate_ocel_log(loop_log([second]))  # raises on a schema violation

    third = loop.run(request)
    assert provider.execute_calls == 2
    assert third.typed_reason == "TYPED_BLOCK_PRIOR_ACTUATION_UNRECONCILED"


def test_r02_refusal_after_actuation_counts_and_blocks_redelivery(court):
    provider = court.ScriptedProvider(effect=court.ok_effect())
    loop, clock = court.make_loop([provider])

    def move_and_expire(p: Any) -> None:
        p.world["gymact"] = court.SHA_B
        clock.advance(10)

    provider.on_execute = move_and_expire
    request = court.make_request(authority=court.make_authority(expires_at_tick=5))
    first = loop.run(request)
    assert first.typed_reason == "REFUSED_CREDENTIAL_EXPIRED"
    assert provider.execute_calls == 1
    assert first.actuation_count == 1
    assert len(_events(first, "actuation")) == 1

    # same request redelivered: the prior actuation is unreconciled
    again = loop.run(request)
    assert provider.execute_calls == 1
    assert again.outcome == "Refuse"  # the grant is still expired: authority gate first
    assert again.actuation_count == 0

    # a renewed grant is a DIFFERENT request under the same key -> key conflict
    renewed = court.make_request(authority=court.make_authority(expires_at_tick=10_000))
    conflict = loop.run(renewed)
    assert provider.execute_calls == 1
    assert conflict.outcome == "Refuse"
    assert conflict.typed_reason == "REFUSED_IDEMPOTENCY_KEY_CONFLICT"
    assert conflict.broken_term == "mu_on_O"
    assert conflict.actuation_count == 0


def test_r03_key_reuse_by_a_different_request_is_refused(court):
    provider = _every_execute_moves(court)
    loop, _ = court.make_loop([provider])
    blocked = loop.run(
        court.make_request(resource_constraints=court.make_constraints(max_subject_moves=1))
    )
    assert blocked.outcome == "TypedBlock"
    other = court.make_request(
        resource_constraints=court.make_constraints(max_subject_moves=3),
        idempotency_key=court.make_request().idempotency_key,
    )
    result = loop.run(other)
    assert provider.execute_calls == 2
    assert result.typed_reason == "REFUSED_IDEMPOTENCY_KEY_CONFLICT"


def test_r04_unreconciled_run_does_not_block_another_work_order(court):
    provider = court.ScriptedProvider(effect=court.ok_effect())
    loop, clock = court.make_loop([provider])
    state = {"n": 0}

    def first_run_expires(p: Any) -> None:
        state["n"] += 1
        if state["n"] == 1:
            p.world["gymact"] = court.SHA_B
            clock.advance(10)

    provider.on_execute = first_run_expires
    failed = loop.run(court.make_request(authority=court.make_authority(expires_at_tick=5)))
    assert failed.actuation_count == 1
    ok = loop.run(
        court.make_request(
            work_order="WO-R04-OTHER", subject=SubjectRef(repo="gymact", sha=court.SHA_B)
        )
    )
    assert ok.outcome == "Recover"
    assert ok.actuation_count == 1
    assert provider.execute_calls == 2


def test_r05_ledger_views_do_not_alias_receipt_evidence(court):
    provider = court.ScriptedProvider(effect=court.ok_effect())
    loop, _ = court.make_loop([provider])
    request = court.make_request()
    result = loop.run(request)
    ledger_before = [dict(e["consequence"]) for e in result.receipt.ext["aloup.actuations"]]
    consequences_before = [dict(c) for c in result.receipt.consequences]

    result.actuations[0]["consequence"]["forged"] = True
    result.receipt.consequences[0]["forged"] = True
    assert [dict(e["consequence"]) for e in result.receipt.ext["aloup.actuations"]] == (
        ledger_before
    )

    replay = loop.run(request)  # dedupe replay of the stored receipt
    assert provider.execute_calls == 1
    assert replay.receipt.ext["aloup.actuations"][0]["consequence"] == ledger_before[0]
    # the direct receipt field mutation stays local to the caller's copy
    assert consequences_before[0] == {
        k: v for k, v in result.receipt.consequences[0].items() if k != "forged"
    }


@pytest.mark.parametrize(
    "value",
    [
        chr(0x200B),
        chr(0xFEFF),
        chr(0x200D) + chr(0x200C),
        chr(0x3000),
        chr(0xA0),
        chr(0x2028),
        " " + chr(0x200B) + "\t",
    ],
)
def test_r06_invisible_identity_fields_are_refused(court, value):
    with pytest.raises(ValidationError):
        court.make_request(work_order=value)
    with pytest.raises(ValidationError):
        court.make_request(capability_requirements=[value])


@pytest.mark.parametrize("evidence", [[], [""], ["  "], [chr(0x200B)]])
def test_r06b_empty_or_blank_evidence_requirements_are_refused(evidence):
    with pytest.raises(ValidationError):
        ExecutionRequest(
            work_order="WO-R06",
            capability_requirements=["exec"],
            subject={"repo": "gymact", "sha": "a" * 40},
            authority=AuthorityGrant(ceiling="DO", grant="court", actor="r06"),
            evidence_requirements=evidence,
        )


def test_r06c_visible_identity_with_surrounding_space_is_admitted(court):
    request = court.make_request(work_order=" WO-\u00e9 ", evidence_requirements=["verifier"])
    assert request.work_order == " WO-\u00e9 "
