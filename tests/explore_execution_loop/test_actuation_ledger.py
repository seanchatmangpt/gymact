"""Actuation-ledger court for the ALOOP execution kernel (PR #148 repair).

Attacks the exactly-once / receipted-consequence claim on the replan paths,
the moving-subject attribution law, the journal-reconstruction path, and the
authority-expiry boundary. All collaborators are the court's real in-process
fakes (``ScriptedProvider``, ``FakeVerifier``, virtual clock); assertions are
on real resulting state: LoopResult fields, receipts, OCEL events and the
provider's own execute counter and journal.

* A01 replan after a moving subject: both actuations are counted, logged as
  ``actuation`` events and receipted (the first as superseded).
* A02 post-verify silent mutation: the already-verified first effect is not
  hidden; count == provider execute calls.
* A03 the kernel derives the count itself: an effect reporting
  ``actuation_count`` 0 (or 7) does not change it.
* A04 an actuation that makes its own declared commit completes in ONE
  actuation (no self-inflicted replan).
* A05 every execute moving the subject typed-blocks with the true count.
* A06 the journal-reconstruction path runs the moving-subject check.
* A07 authority that expires between claim and execute refuses with zero
  actuation (pre-execute expiry gate).
* A08 expiry boundary: ``expires_at_tick == now`` is expired; ``now + 1`` is not.
* A09 blank work orders / capabilities are refused at construction.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from gymact.execution_loop import (
    AuthorityGrant,
    AutonomousLoop,
    ClaimPin,
    ExecutionRequest,
    SubjectRef,
    loop_log,
)
from gymact.ocel import validate_ocel_log


def _actuation_events(result: Any) -> list[Any]:
    return [event for event in result.events if event.event_type == "actuation"]


def _assert_conserved(result: Any, provider: Any) -> None:
    assert result.actuation_count == provider.execute_calls
    assert result.actuation_count == len(provider.journal)
    assert len(_actuation_events(result)) == result.actuation_count
    assert len(result.actuations) == result.actuation_count


def test_a01_moving_subject_replan_counts_and_receipts_both_actuations(court):
    built = court.BUILDERS["L7-F14-moving-subject-single-move"](7, inject=True)
    [result] = built.run()
    provider = built.providers[0]
    assert result.outcome == "Recover"
    assert provider.execute_calls == 2
    _assert_conserved(result, provider)
    receipt = result.receipt
    assert receipt is not None
    assert len(receipt.commands) == 2
    assert len(receipt.consequences) == 2
    dispositions = [entry["disposition"] for entry in receipt.ext["aloup.actuations"]]
    assert dispositions == ["superseded", "admitted"]
    assert receipt.ext["aloup.actuations"][1]["provider_execution_id"] == (
        receipt.provider_execution_id
    )
    # the receipt names the witnessed subject, not the provider's stale claim
    assert receipt.subject_after["sha"] == court.SHA_B
    validate_ocel_log(loop_log([result], seed=7))


def test_a02_post_verify_silent_mutation_does_not_hide_the_verified_first_effect(court):
    built = court.BUILDERS["L7-F27-silent-external-state-mutation"](7, inject=True)
    [result] = built.run()
    provider = built.providers[0]
    assert result.outcome == "Recover"
    assert provider.execute_calls == 2
    _assert_conserved(result, provider)
    types = [event.event_type for event in result.events]
    # first actuation -> verification -> replan -> second actuation
    first = types.index("actuation")
    assert types.index("verification", first) < types.index("reconcile.replan", first)
    assert types.count("actuation") == 2


def test_a02b_lifegym_silent_stage_mutation_counts_both_actuations(court):
    built = court.BUILDERS["L7-F31-lifegym-long-horizon-silent-stage-mutation"](7, inject=True)
    [result] = built.run()
    world = built.providers[0]
    assert result.outcome == "Recover"
    assert world.execute_calls == 2
    assert result.actuation_count == 2 == len(world.journal)


@pytest.mark.parametrize("reported", [0, 7])
def test_a03_actuation_count_is_kernel_derived_not_provider_reported(court, reported):
    effect = dict(court.ok_effect(), actuation_count=reported)
    provider = court.ScriptedProvider(effect=effect)
    loop, _ = court.make_loop([provider])
    result = loop.run(court.make_request())
    assert result.outcome == "Recover"
    assert result.actuation_count == 1
    _assert_conserved(result, provider)


def test_a04_actuation_owned_commit_is_one_actuation_not_a_replan(court):
    def commit(provider: Any) -> None:
        provider.world["gymact"] = court.SHA_B

    provider = court.ScriptedProvider(on_execute=commit, effect=court.ok_effect(court.SHA_B))
    loop, _ = court.make_loop([provider])
    result = loop.run(court.make_request())
    assert result.outcome == "Recover"
    assert provider.execute_calls == 1
    assert "reconcile.replan" not in {event.event_type for event in result.events}
    _assert_conserved(result, provider)
    assert result.receipt is not None
    assert result.receipt.subject_before["sha"] == court.SHA_A
    assert result.receipt.subject_after["sha"] == court.SHA_B


def test_a04b_undeclared_move_is_still_a_move(court):
    """Same world transition, but the effect declares the ORIGINAL subject:
    the move is not attributable to the actuation, so the loop replans."""

    def commit(provider: Any) -> None:
        provider.world["gymact"] = court.SHA_B

    provider = court.ScriptedProvider(on_execute=commit, effect=court.ok_effect(court.SHA_A))
    loop, _ = court.make_loop([provider])
    result = loop.run(court.make_request())
    assert "reconcile.replan" in {event.event_type for event in result.events}
    _assert_conserved(result, provider)


def test_a05_every_execute_moving_the_subject_typed_blocks_with_true_count(court):
    def move_every(provider: Any) -> None:
        current = provider.world["gymact"]
        provider.world["gymact"] = court.SHA_B if current == court.SHA_A else court.SHA_C

    provider = court.ScriptedProvider(on_execute=move_every, effect=court.ok_effect())
    loop, _ = court.make_loop([provider])
    request = court.make_request(resource_constraints=court.make_constraints(max_subject_moves=1))
    result = loop.run(request)
    assert result.outcome == "TypedBlock"
    assert result.typed_reason == "TYPED_BLOCK_MOVING_SUBJECT"
    assert provider.execute_calls == 2
    _assert_conserved(result, provider)


class _MovingJournalProvider:
    """fetch_receipt moves the world: an external writer lands a commit while
    the loop reconstructs a post-actuation crash from the journal."""

    def __init__(self, court: Any) -> None:
        self.inner = court.ScriptedProvider(
            execute_faults=[("crash_after_actuation",)], effect=court.ok_effect()
        )
        self.sha_c = court.SHA_C
        self.moved = False
        for name in (
            "transport",
            "capabilities",
            "authority_ceiling",
            "availability",
            "cost",
            "concurrency",
            "receipt_protocol",
        ):
            setattr(self, name, getattr(self.inner, name))

    @property
    def journal(self) -> dict[str, Any]:
        return self.inner.journal

    @property
    def execute_calls(self) -> int:
        return self.inner.execute_calls

    def current_subject_sha(self, repo: str) -> str:
        return self.inner.current_subject_sha(repo)

    def resolve_subject(self, repo: str) -> SubjectRef:
        return self.inner.resolve_subject(repo)

    def claim(self, request: ExecutionRequest) -> ClaimPin:
        return self.inner.claim(request)

    def execute(self, request: ExecutionRequest, provider_execution_id: str) -> dict[str, Any]:
        return self.inner.execute(request, provider_execution_id)

    def fetch_receipt(self, provider_execution_id: str) -> dict[str, Any] | None:
        if not self.moved:
            self.moved = True
            self.inner.world["gymact"] = self.sha_c
        return self.inner.fetch_receipt(provider_execution_id)

    def ack(self, receipt: Any) -> None:
        self.inner.ack(receipt)


def test_a06_journal_reconstruction_runs_the_moving_subject_check(court):
    provider = _MovingJournalProvider(court)
    loop, _ = court.make_loop([provider])  # type: ignore[list-item]
    result = loop.run(court.make_request())
    assert "reconcile.replan" in {event.event_type for event in result.events}
    assert result.outcome == "Recover"
    assert result.receipt is not None
    # never an ALIVE receipt claiming the pre-move subject after a move
    assert result.receipt.subject_after["sha"] == court.SHA_C
    assert result.receipt.replay_binding["pinned_subject_sha"] == court.SHA_C
    assert result.actuation_count == provider.execute_calls == len(provider.journal) == 2


def test_a06b_journal_move_beyond_budget_typed_blocks(court):
    provider = _MovingJournalProvider(court)
    loop, _ = court.make_loop([provider])  # type: ignore[list-item]
    request = court.make_request(resource_constraints=court.make_constraints(max_subject_moves=0))
    result = loop.run(request)
    assert result.outcome == "TypedBlock"
    assert result.typed_reason == "TYPED_BLOCK_MOVING_SUBJECT"
    assert result.actuation_count == 1 == provider.execute_calls


class _SlowClaimProvider:
    """A claim that takes ``claim_ticks`` of (virtual) time: the grant can
    expire between claim and execute."""

    def __init__(self, court: Any, clock: Any, claim_ticks: int) -> None:
        self.inner = court.ScriptedProvider(effect=court.ok_effect())
        self.clock = clock
        self.claim_ticks = claim_ticks
        for name in (
            "transport",
            "capabilities",
            "authority_ceiling",
            "availability",
            "cost",
            "concurrency",
            "receipt_protocol",
        ):
            setattr(self, name, getattr(self.inner, name))

    def current_subject_sha(self, repo: str) -> str:
        return self.inner.current_subject_sha(repo)

    def resolve_subject(self, repo: str) -> SubjectRef:
        return self.inner.resolve_subject(repo)

    def claim(self, request: ExecutionRequest) -> ClaimPin:
        pin = self.inner.claim(request)
        self.clock.advance(self.claim_ticks)
        return pin

    def execute(self, request: ExecutionRequest, provider_execution_id: str) -> dict[str, Any]:
        return self.inner.execute(request, provider_execution_id)

    def fetch_receipt(self, provider_execution_id: str) -> dict[str, Any] | None:
        return self.inner.fetch_receipt(provider_execution_id)

    def ack(self, receipt: Any) -> None:
        self.inner.ack(receipt)


def _loop_with_clock(court: Any, provider_factory: Any, tick: int = 0) -> tuple[Any, Any]:
    clock = court.VirtualClock()
    clock.tick = tick
    provider = provider_factory(clock)
    loop = AutonomousLoop(
        [provider],
        court.FakeVerifier(),
        court.FakeRegistry(),
        court.FakeProbe(),
        clock=clock.now,
        advance=clock.advance,
    )
    return loop, provider


def test_a07_grant_expiring_between_claim_and_execute_refuses_with_zero_actuation(court):
    loop, provider = _loop_with_clock(
        court, lambda clock: _SlowClaimProvider(court, clock, claim_ticks=5)
    )
    request = court.make_request(authority=court.make_authority(expires_at_tick=3))
    result = loop.run(request)
    assert result.outcome == "Refuse"
    assert result.typed_reason == "REFUSED_CREDENTIAL_EXPIRED"
    assert provider.inner.claim_calls == 1
    assert provider.inner.execute_calls == 0
    assert result.actuation_count == 0
    assert _actuation_events(result) == []


def test_a08_expiry_boundary_now_equals_expires_is_expired(court):
    provider = court.ScriptedProvider(effect=court.ok_effect())
    loop, _ = _loop_with_clock(court, lambda clock: provider, tick=5)
    result = loop.run(court.make_request(authority=court.make_authority(expires_at_tick=5)))
    assert result.outcome == "Refuse"
    assert result.typed_reason == "REFUSED_CREDENTIAL_EXPIRED"
    assert provider.execute_calls == 0


def test_a08b_expiry_boundary_one_tick_before_is_valid(court):
    provider = court.ScriptedProvider(effect=court.ok_effect())
    loop, _ = _loop_with_clock(court, lambda clock: provider, tick=5)
    result = loop.run(court.make_request(authority=court.make_authority(expires_at_tick=6)))
    assert result.outcome == "Recover"
    assert provider.execute_calls == 1


@pytest.mark.parametrize(
    "over",
    [
        {"work_order": "   "},
        {"work_order": "\t\n"},
        {"capability_requirements": []},
        {"capability_requirements": [" "]},
        {"subject": {"repo": "  ", "sha": "a" * 40}},
    ],
)
def test_a09_blank_identity_fields_are_refused_at_construction(court, over):
    fields: dict[str, Any] = {
        "work_order": "WO-A09",
        "capability_requirements": ["exec"],
        "subject": {"repo": "gymact", "sha": "a" * 40},
        "authority": AuthorityGrant(ceiling="DO", grant="court", actor="a09"),
        "evidence_requirements": ["verifier"],
    }
    fields.update(over)
    with pytest.raises(ValidationError):
        ExecutionRequest(**fields)
