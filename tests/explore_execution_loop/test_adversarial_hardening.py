"""Adversarial hardening court for the ALOOP execution kernel (PR #148).

Each test attacks one claimed capability of ``gymact.execution_loop`` with
input the fault corpus does not cover, and asserts on the REAL resulting
state (LoopResult fields, provider actuation counters, receipts). All
collaborators are real, simple in-process implementations of the kernel's
protocols (no interaction mocks); determinism comes from a virtual clock.

Attacks (each was a live defect or an unwitnessed guard before this court):

* H01 idempotency-key collision: a second, DIFFERENT request reusing a
  completed request's idempotency key must be refused, never answered with
  the other request's receipt (mu_on_O).
* H02 authority expiring during backoff: a grant valid at start but expired
  by the time the loop would claim must be refused with zero actuation.
* H03 journal-reconstructed receipt with a wrong digest: a receipt rebuilt
  after a post-actuation crash must pass the verifier like any other receipt.
* H04 effect without an effect digest: a provider returning no digest can
  never yield an ALIVE receipt.
* H05 malformed requests: empty work order, empty repo, non-hex SHA and
  negative budgets are rejected at construction.
* H06 unknown authority ceilings fail closed (no actuation).
* H07 duplicate delivery and reordering: across any delivery order each
  distinct work order actuates exactly once and duplicates actuate zero times.
* H08 replay: the same scenario replayed twice yields byte-identical OCEL
  logs and receipts.
"""

from __future__ import annotations

import itertools
import json
from typing import Any

import pytest
from pydantic import ValidationError

from gymact.evidence import digest
from gymact.execution_loop import (
    AuthorityGrant,
    AutonomousLoop,
    BrokenTerm,
    ClaimPin,
    ExecutionReceipt,
    ExecutionRequest,
    LegalOutcome,
    ResourceConstraints,
    SubjectRef,
    TransportFault,
    WorkerCrashed,
    loop_log,
)
from gymact.models import Standing
from gymact.ocel import validate_ocel_log

SHA_A = "a" * 40
GOOD_DIGEST = "de" * 8


class Clock:
    def __init__(self, tick: int = 0) -> None:
        self.tick = tick

    def now(self) -> int:
        return self.tick

    def advance(self, ticks: int) -> None:
        self.tick += ticks


class Registry:
    def is_valid(self, grant: AuthorityGrant) -> bool:
        return True


class Probe:
    def disk_mb_available(self) -> int:
        return 10_000

    def cpu_cores_available(self) -> float:
        return 8.0


class DigestVerifier:
    """Real verifier: accepts exactly one expected effect digest."""

    def __init__(self, expected: str = GOOD_DIGEST) -> None:
        self.expected = expected

    def verify(
        self, subject_after: SubjectRef, effect_digest: str, request: ExecutionRequest
    ) -> tuple[bool, str]:
        if effect_digest == self.expected:
            return True, "digest matches"
        return False, f"digest mismatch {effect_digest!r}"


class Provider:
    """Journaling provider. ``claim_faults`` / ``execute_faults`` are consumed
    one per call; ``effect`` is what an actuation returns and journals."""

    capabilities = ("exec",)
    availability = True
    cost = 0.0
    concurrency = 1
    receipt_protocol = "journal"

    def __init__(
        self,
        *,
        transport: str = "local:primary",
        authority_ceiling: str = "DO",
        effect: dict[str, Any] | None = None,
        claim_faults: list[Exception] | None = None,
        execute_faults: list[Exception] | None = None,
    ) -> None:
        self.transport = transport
        self.authority_ceiling = authority_ceiling
        self.effect = (
            effect
            if effect is not None
            else {"effect_digest": GOOD_DIGEST, "subject_after_sha": SHA_A, "actuation_count": 1}
        )
        self.claim_faults = list(claim_faults or [])
        self.execute_faults = list(execute_faults or [])
        self.claims = 0
        self.actuations: list[str] = []  # work orders actually actuated
        self.journal: dict[str, dict[str, Any]] = {}

    def current_subject_sha(self, repo: str) -> str:
        return SHA_A

    def resolve_subject(self, repo: str) -> SubjectRef:
        return SubjectRef(repo=repo, sha=SHA_A)

    def claim(self, request: ExecutionRequest) -> ClaimPin:
        self.claims += 1
        if self.claim_faults:
            raise self.claim_faults.pop(0)
        return ClaimPin(
            provider_execution_id=f"{self.transport}/{request.work_order}/{self.claims}",
            pinned_subject_sha=SHA_A,
        )

    def execute(self, request: ExecutionRequest, provider_execution_id: str) -> dict[str, Any]:
        if self.execute_faults:
            fault = self.execute_faults.pop(0)
            if isinstance(fault, WorkerCrashed) and fault.applied_before:
                self.actuations.append(request.work_order)
                self.journal[provider_execution_id] = dict(self.effect)
            raise fault
        self.actuations.append(request.work_order)
        self.journal[provider_execution_id] = dict(self.effect)
        return dict(self.effect)

    def fetch_receipt(self, provider_execution_id: str) -> dict[str, Any] | None:
        return self.journal.get(provider_execution_id)

    def ack(self, receipt: ExecutionReceipt) -> None:
        return None


def make_loop(
    providers: list[Provider], *, verifier: DigestVerifier | None = None, tick: int = 0
) -> tuple[AutonomousLoop, Clock]:
    clock = Clock(tick)
    loop = AutonomousLoop(
        providers,
        verifier or DigestVerifier(),
        Registry(),
        Probe(),
        clock=clock.now,
        advance=clock.advance,
    )
    return loop, clock


def request(work_order: str = "WO-H-001", **over: Any) -> ExecutionRequest:
    fields: dict[str, Any] = {
        "work_order": work_order,
        "capability_requirements": ["exec"],
        "subject": SubjectRef(repo="gymact", sha=SHA_A),
        "authority": AuthorityGrant(ceiling="CONSTRUCT", grant="court", actor="hardening"),
        "evidence_requirements": ["verifier"],
    }
    fields.update(over)
    return ExecutionRequest(**fields)


# --------------------------------------------------------------------------- #
# H01 idempotency-key collision
# --------------------------------------------------------------------------- #


def test_h01_idempotency_key_collision_is_refused_not_answered_with_foreign_receipt():
    provider = Provider()
    loop, _ = make_loop([provider])
    first = loop.run(request("WO-H-A", idempotency_key="shared-key"))
    assert first.outcome == LegalOutcome.RECOVER.value
    assert first.receipt is not None

    second = loop.run(request("WO-H-B", idempotency_key="shared-key"))

    assert second.outcome == LegalOutcome.REFUSE.value, second
    assert second.typed_reason == "REFUSED_IDEMPOTENCY_KEY_CONFLICT"
    assert second.broken_term is BrokenTerm.MU_ON_O
    assert second.receipt is None
    assert second.actuation_count == 0
    assert provider.actuations == ["WO-H-A"]


def test_h01_same_request_redelivered_still_deduplicates():
    provider = Provider()
    loop, _ = make_loop([provider])
    wo = request("WO-H-DUP")
    first = loop.run(wo)
    again = loop.run(request("WO-H-DUP"))  # equal content, new object
    assert again.outcome == LegalOutcome.RECOVER.value
    assert again.receipt == first.receipt
    assert again.actuation_count == 0
    assert provider.actuations == ["WO-H-DUP"]


def test_h01_same_key_different_subject_sha_is_refused():
    provider = Provider()
    loop, _ = make_loop([provider])
    loop.run(request("WO-H-S"))
    moved = loop.run(request("WO-H-S", subject=SubjectRef(repo="gymact", sha="b" * 40)))
    assert moved.typed_reason == "REFUSED_IDEMPOTENCY_KEY_CONFLICT"
    assert provider.actuations == ["WO-H-S"]


# --------------------------------------------------------------------------- #
# H02 authority expiring during backoff
# --------------------------------------------------------------------------- #


def test_h02_authority_expiring_during_backoff_refuses_before_actuation():
    provider = Provider(
        claim_faults=[TransportFault(kind="rate_limit", retry_after_ticks=2)] * 2,
    )
    loop, clock = make_loop([provider])
    grant = AuthorityGrant(ceiling="CONSTRUCT", grant="court", actor="h02", expires_at_tick=4)
    result = loop.run(request("WO-H-EXP", authority=grant))

    assert clock.tick >= 4, "the scenario must actually cross the expiry tick"
    assert result.outcome == LegalOutcome.REFUSE.value, result
    assert result.typed_reason == "REFUSED_CREDENTIAL_EXPIRED"
    assert result.broken_term is BrokenTerm.R_MISSING_AUTHORITY
    assert result.actuation_count == 0
    assert provider.actuations == []


def test_h02_authority_still_valid_after_backoff_recovers():
    """Anti-vacuity twin: same faults, later expiry -> actuates once."""
    provider = Provider(
        claim_faults=[TransportFault(kind="rate_limit", retry_after_ticks=2)] * 2,
    )
    loop, _ = make_loop([provider])
    grant = AuthorityGrant(ceiling="CONSTRUCT", grant="court", actor="h02", expires_at_tick=500)
    result = loop.run(request("WO-H-EXP2", authority=grant))
    assert result.outcome == LegalOutcome.RECOVER.value
    assert provider.actuations == ["WO-H-EXP2"]


# --------------------------------------------------------------------------- #
# H03 journal-reconstructed receipt must be verified
# --------------------------------------------------------------------------- #


def test_h03_reconstructed_receipt_with_wrong_digest_is_not_alive():
    provider = Provider(
        effect={"effect_digest": "ff" * 8, "subject_after_sha": SHA_A, "actuation_count": 1},
        execute_faults=[WorkerCrashed(applied_before=True, injection_point="post-actuation")],
    )
    loop, _ = make_loop([provider])
    result = loop.run(request("WO-H-JRN"))

    assert result.standing is not Standing.ALIVE, result
    assert result.outcome == LegalOutcome.TYPED_BLOCK.value
    assert result.broken_term is BrokenTerm.VERIFICATION_FAILED
    assert result.receipt is None
    assert provider.actuations == ["WO-H-JRN"], "must never re-actuate after the crash"


def test_h03_reconstructed_receipt_with_good_digest_recovers_exactly_once():
    provider = Provider(
        execute_faults=[WorkerCrashed(applied_before=True, injection_point="post-actuation")],
    )
    loop, _ = make_loop([provider])
    result = loop.run(request("WO-H-JRN2"))
    assert result.outcome == LegalOutcome.RECOVER.value
    assert result.standing is Standing.ALIVE
    assert result.actuation_count == 1
    assert provider.actuations == ["WO-H-JRN2"]


# --------------------------------------------------------------------------- #
# H04 missing effect digest
# --------------------------------------------------------------------------- #


class AcceptAnything:
    def verify(
        self, subject_after: SubjectRef, effect_digest: str, request: ExecutionRequest
    ) -> tuple[bool, str]:
        return True, "permissive"


@pytest.mark.parametrize("effect", [{}, {"effect_digest": ""}, {"effect_digest": None}])
def test_h04_effect_without_digest_never_yields_alive_even_with_permissive_verifier(effect):
    provider = Provider(effect=dict(effect, subject_after_sha=SHA_A))
    clock = Clock()
    loop = AutonomousLoop(
        [provider], AcceptAnything(), Registry(), Probe(), clock=clock.now, advance=clock.advance
    )
    result = loop.run(request("WO-H-NODIG"))
    assert result.standing is not Standing.ALIVE, result
    assert result.outcome == LegalOutcome.TYPED_BLOCK.value
    assert result.broken_term is BrokenTerm.R_MISSING_CONSEQUENCE
    assert result.typed_reason == "TYPED_BLOCK_EFFECT_DIGEST_MISSING"
    assert result.receipt is None


# --------------------------------------------------------------------------- #
# H05 malformed input
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "over",
    [
        {"work_order": ""},
        {"subject": {"repo": "", "sha": SHA_A}},
        {"subject": {"repo": "gymact", "sha": ""}},
        {"subject": {"repo": "gymact", "sha": "not-a-sha"}},
        {"subject": {"repo": "gymact", "sha": "A" * 40}},
        {"resource_constraints": {"max_retries": -1}},
        {"resource_constraints": {"deadline_ticks": -5}},
        {"resource_constraints": {"max_provider_switches": -1}},
        {"resource_constraints": {"max_subject_moves": -1}},
        {"capability_requirements": [""]},
    ],
    ids=lambda over: json.dumps(over, sort_keys=True),
)
def test_h05_malformed_request_is_rejected_at_construction(over):
    with pytest.raises(ValidationError):
        request(**over)


def test_h05_well_formed_boundaries_are_admitted():
    # 7..64 lowercase hex, zero budgets are legal (they typed-block, not crash)
    request(subject=SubjectRef(repo="gymact", sha="abcdef0"))
    request(subject=SubjectRef(repo="gymact", sha="0" * 64))
    request(resource_constraints=ResourceConstraints(max_retries=0, max_subject_moves=0))


def test_h05_zero_deadline_is_a_typed_block_not_a_hang():
    provider = Provider()
    loop, _ = make_loop([provider])
    result = loop.run(request(resource_constraints=ResourceConstraints(deadline_ticks=0)))
    assert result.outcome == LegalOutcome.TYPED_BLOCK.value
    assert result.typed_reason == "TYPED_BLOCK_BUDGET_EXHAUSTED"
    assert provider.actuations == []


# --------------------------------------------------------------------------- #
# H06 unknown ceilings fail closed
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("ceiling", ["ROOT", "", "admin", "D0"])
def test_h06_unknown_requested_ceiling_fails_closed(ceiling):
    provider = Provider()
    loop, _ = make_loop([provider])
    grant = AuthorityGrant(ceiling=ceiling, grant="court", actor="h06")
    result = loop.run(request("WO-H-CEIL", authority=grant))
    assert result.outcome == LegalOutcome.REFUSE.value
    assert result.typed_reason == "REFUSED_IMPOSSIBLE_OBJECTIVE"
    assert provider.actuations == []


def test_h06_provider_with_unknown_ceiling_is_never_selected():
    provider = Provider(authority_ceiling="SUPERUSER")
    loop, _ = make_loop([provider])
    result = loop.run(request("WO-H-CEIL2"))
    assert result.outcome == LegalOutcome.REFUSE.value
    assert provider.actuations == []


# --------------------------------------------------------------------------- #
# H07 duplicate delivery x reordering
# --------------------------------------------------------------------------- #


def test_h07_every_delivery_order_actuates_each_work_order_exactly_once():
    base = ["WO-H-R1", "WO-H-R2", "WO-H-R3"]
    deliveries = [*base, "WO-H-R1", "WO-H-R3"]  # two duplicate deliveries
    seen_receipt_shapes: set[str] = set()
    for order in set(itertools.permutations(deliveries)):
        provider = Provider()
        loop, _ = make_loop([provider])
        results = [loop.run(request(wo)) for wo in order]
        assert sorted(provider.actuations) == sorted(base), order
        assert sum(r.actuation_count for r in results) == len(base), order
        assert all(r.outcome == LegalOutcome.RECOVER.value for r in results)
        by_wo: dict[str, set[str]] = {}
        for wo, result in zip(order, results, strict=True):
            assert result.receipt is not None
            assert result.receipt.work_order_id == wo
            by_wo.setdefault(wo, set()).add(result.receipt.provider_execution_id)
        # a duplicate is answered with THE receipt of its own first delivery
        assert all(len(ids) == 1 for ids in by_wo.values()), by_wo
        seen_receipt_shapes.add(
            digest(sorted((r.receipt.work_order_id, r.receipt.exit_status) for r in results))
        )
    assert len(seen_receipt_shapes) == 1


# --------------------------------------------------------------------------- #
# H08 replay determinism
# --------------------------------------------------------------------------- #


def _replayable_run() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    primary = Provider(
        transport="local:primary",
        claim_faults=[TransportFault(kind="provider_unavailable")] * 4,
    )
    backup = Provider(
        transport="local:backup",
        execute_faults=[WorkerCrashed(applied_before=False, injection_point="pre")],
    )
    loop, _ = make_loop([primary, backup])
    results = [loop.run(request("WO-H-REPLAY")), loop.run(request("WO-H-REPLAY"))]
    return loop_log(results, seed=7), [r.model_dump(mode="json") for r in results]


def test_h08_replay_is_byte_identical_and_ocel_valid():
    log_a, results_a = _replayable_run()
    log_b, results_b = _replayable_run()
    validate_ocel_log(log_a)
    assert digest(log_a) == digest(log_b)
    assert digest(results_a) == digest(results_b)
    # the replayed run genuinely substituted (not a trivially-healthy replay)
    assert results_a[0]["receipt"]["provider"]["transport"] == "local:backup"
    assert results_a[1]["actuation_count"] == 0
