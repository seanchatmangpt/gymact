"""Lane-7 fault-scenario court: deterministic in-process fakes and scenario
builders for the ALOOP-ZCODE-DOGFOOD-001 execution-loop corpus.

Everything here is simulated-in-process (no external dependency, no network,
no real worker); determinism comes from scripted fault lists and seed-drawn
parameters only -- no wall clock, no OS entropy. ``random.Random(seed)`` is
the sole randomness source and is only used by scenarios that declare seeds.

The ``inject`` flag on every builder is the anti-vacuity control: the same
scenario built with ``inject=False`` is the MUTANT (fault NOT injected) that
``test_antivacuity.py`` uses to prove each recovery court carries bits.
"""

from __future__ import annotations

import json
import random
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import pytest

from gymact.evidence import digest
from gymact.execution_loop import (
    AuthorityGrant,
    AutonomousLoop,
    ClaimPin,
    ExecutionReceipt,
    ExecutionRequest,
    ResourceConstraints,
    SubjectRef,
    TransportFault,
    WorkerCrashed,
)

SHA_A = "a" * 40
SHA_B = "b" * 40
SHA_C = "c" * 40

COURT_DIR = Path(__file__).parent


def load_manifest() -> dict[str, Any]:
    return json.loads((COURT_DIR / "scenario_manifest.json").read_text())


# --------------------------------------------------------------------------- #
# Deterministic fakes
# --------------------------------------------------------------------------- #


class VirtualClock:
    """Deterministic virtual clock; the loop advances it via backoff only."""

    def __init__(self) -> None:
        self.tick = 0

    def now(self) -> int:
        return self.tick

    def advance(self, ticks: int) -> None:
        self.tick += ticks


class FakeRegistry:
    def __init__(self, valid: bool = True) -> None:
        self.valid = valid

    def is_valid(self, grant: AuthorityGrant) -> bool:
        return self.valid


class FakeProbe:
    def __init__(self, disk_mb: int = 10_000, cpu_cores: float = 8.0) -> None:
        self.disk_mb = disk_mb
        self.cpu_cores = cpu_cores

    def disk_mb_available(self) -> int:
        return self.disk_mb

    def cpu_cores_available(self) -> float:
        return self.cpu_cores


class FakeVerifier:
    """Scripted verify results; the last entry repeats. ``on_verify`` is a
    side-effect hook (used by silent-mutation scenarios: the 'external
    process' that mutates state is the verifier itself)."""

    def __init__(
        self,
        results: list[tuple[bool, str]] | None = None,
        on_verify: Callable[[], None] | None = None,
    ) -> None:
        self.results = list(results or [(True, "ok")])
        self.on_verify = on_verify
        self.calls = 0

    def verify(
        self, subject_after: SubjectRef, effect_digest: str, request: ExecutionRequest
    ) -> tuple[bool, str]:
        self.calls += 1
        if self.on_verify is not None:
            self.on_verify()
        index = min(self.calls - 1, len(self.results) - 1)
        return self.results[index]


class ScriptedProvider:
    """In-process provider with scripted faults. Fault lists are consumed
    left-to-right one per call; once empty the provider behaves healthily.
    World state (``world[repo]``) is the subject SHA the outside world sees;
    scenarios move it via ``on_execute`` hooks or directly."""

    def __init__(
        self,
        transport: str = "fake:primary",
        *,
        capabilities: tuple[str, ...] = ("exec",),
        authority_ceiling: str = "DO",
        availability: bool = True,
        receipt_protocol: str = "fake+journal",
        world: dict[str, str] | None = None,
        claim_faults: list[Any] | None = None,
        execute_faults: list[Any] | None = None,
        ack_faults: list[Any] | None = None,
        journal_lost: bool = False,
        on_execute: Callable[["ScriptedProvider"], None] | None = None,
        effect: dict[str, Any] | None = None,
    ):
        self.transport = transport
        self.capabilities = list(capabilities)
        self.authority_ceiling = authority_ceiling
        self.availability = availability
        self.cost = 0.0
        self.concurrency = 1
        self.receipt_protocol = receipt_protocol
        self.world = world if world is not None else {"gymact": SHA_A}
        self.claim_faults = deque(claim_faults or [])
        self.execute_faults = deque(execute_faults or [])
        self.ack_faults = deque(ack_faults or [])
        self.journal_lost = journal_lost
        self.on_execute = on_execute
        self.effect = effect or {}
        self.claim_calls = 0
        self.execute_calls = 0
        self.ack_calls = 0
        self.journal: dict[str, dict[str, Any]] = {}

    # -- protocol surface ---------------------------------------------------

    def current_subject_sha(self, repo: str) -> str:
        return self.world.get(repo, SHA_A)

    def resolve_subject(self, repo: str) -> SubjectRef:
        return SubjectRef(repo=repo, sha=self.current_subject_sha(repo))

    def claim(self, request: ExecutionRequest) -> ClaimPin:
        self.claim_calls += 1
        fault = self.claim_faults.popleft() if self.claim_faults else None
        if fault is not None:
            kind = fault[0] if isinstance(fault, tuple) else fault
            retry = fault[1] if isinstance(fault, tuple) and len(fault) > 1 else 1
            if kind == "worker_sigkill":
                raise WorkerCrashed(applied_before=False, injection_point="mid-claim")
            raise TransportFault(kind=kind, retry_after_ticks=retry)
        return ClaimPin(
            provider_execution_id=f"{self.transport}/{request.work_order}/{self.claim_calls}",
            pinned_subject_sha=self.current_subject_sha(request.subject.repo),
        )

    def execute(self, request: ExecutionRequest, provider_execution_id: str) -> dict[str, Any]:
        self.execute_calls += 1
        fault = self.execute_faults.popleft() if self.execute_faults else None
        if fault is not None:
            if fault[0] == "crash_before_actuation":
                raise WorkerCrashed(applied_before=False, injection_point="pre-actuation")
            if fault[0] == "crash_after_actuation":
                # actuation happens, the durable journal fragment is written,
                # and THEN the worker dies before the receipt exists.
                self.journal[provider_execution_id] = self._fragment()
                raise WorkerCrashed(
                    applied_before=True, injection_point="post-actuation-pre-receipt"
                )
            raise TransportFault(kind=fault[1], retry_after_ticks=fault[2] if len(fault) > 2 else 1)
        if self.on_execute is not None:
            self.on_execute(self)
        self.journal[provider_execution_id] = self._fragment()
        return self._fragment()

    def fetch_receipt(self, provider_execution_id: str) -> dict[str, Any] | None:
        if self.journal_lost:
            return None
        return self.journal.get(provider_execution_id)

    def ack(self, receipt: ExecutionReceipt) -> None:
        self.ack_calls += 1
        if self.ack_faults:
            self.ack_faults.popleft()
            raise TransportFault(kind="lost_ack", retry_after_ticks=1)

    def _fragment(self) -> dict[str, Any]:
        return dict(self.effect)


# --------------------------------------------------------------------------- #
# Request/loop factories
# --------------------------------------------------------------------------- #


def make_authority(**over: Any) -> AuthorityGrant:
    fields: dict[str, Any] = {
        "ceiling": "DO",
        "grant": "operator-dispatch ALOOP-ZCODE-DOGFOOD-001 lane-7",
        "actor": "lane-7",
    }
    fields.update(over)
    return AuthorityGrant(**fields)


def make_constraints(**over: Any) -> ResourceConstraints:
    fields: dict[str, Any] = {}
    fields.update(over)
    return ResourceConstraints(**fields)


def make_request(**over: Any) -> ExecutionRequest:
    fields: dict[str, Any] = {
        "work_order": "WO-L7-001",
        "capability_requirements": ["exec"],
        "subject": SubjectRef(repo="gymact", sha=SHA_A),
        "authority": make_authority(),
        "evidence_requirements": ["verifier"],
    }
    fields.update(over)
    return ExecutionRequest(**fields)


def make_loop(
    providers: list[ScriptedProvider],
    verifier: FakeVerifier | None = None,
    registry: FakeRegistry | None = None,
    probe: FakeProbe | None = None,
) -> tuple[AutonomousLoop, VirtualClock]:
    clock = VirtualClock()
    loop = AutonomousLoop(
        providers,
        verifier or FakeVerifier(),
        registry or FakeRegistry(),
        probe or FakeProbe(),
        clock=clock.now,
        advance=clock.advance,
    )
    return loop, clock


@dataclass
class Built:
    """One built scenario: loop + requests to run in order + optional
    scenario-specific post-asserts over the resulting LoopResults."""

    scenario_id: str
    loop: AutonomousLoop
    requests: list[ExecutionRequest]
    clock: VirtualClock
    providers: list[ScriptedProvider] = field(default_factory=list)
    post: Callable[[list[Any]], None] | None = None

    def run(self) -> list[Any]:
        return [self.loop.run(request) for request in self.requests]


def ok_effect(sha: str = SHA_A) -> dict[str, Any]:
    return {
        "effect_digest": "de" * 8,
        "subject_after_sha": sha,
        "actuation_count": 1,
        "consequence": {"changed_files": 1, "work": "simulated"},
    }


# --------------------------------------------------------------------------- #
# Scenario builders (registry keyed by manifest scenario id)
# --------------------------------------------------------------------------- #


def _b_crash_before(seed: int, inject: bool) -> Built:
    primary = ScriptedProvider(
        execute_faults=[("crash_before_actuation",)] if inject else [],
        effect=ok_effect(),
    )
    loop, clock = make_loop([primary])
    return Built(
        "L7-F01-worker-sigkill-before-actuation",
        loop,
        [make_request()],
        clock,
        [primary],
    )


def _b_crash_after_journal(seed: int, inject: bool) -> Built:
    primary = ScriptedProvider(
        execute_faults=[("crash_after_actuation",)] if inject else [],
        effect=ok_effect(),
    )
    loop, clock = make_loop([primary])
    return Built(
        "L7-F02-worker-sigkill-after-actuation-journal-present",
        loop,
        [make_request()],
        clock,
        [primary],
        post=lambda results: (
            results[0].actuation_count == 1 and primary.execute_calls == 1
        )
        or (_ for _ in ()).throw(
            AssertionError(
                f"exactly-once violated: actuation_count={results[0].actuation_count} "
                f"execute_calls={primary.execute_calls}"
            )
        ),
    )


def _b_crash_after_journal_lost(seed: int, inject: bool) -> Built:
    primary = ScriptedProvider(
        execute_faults=[("crash_after_actuation",)] if inject else [],
        journal_lost=True,
        effect=ok_effect(),
    )
    loop, clock = make_loop([primary])
    return Built(
        "L7-F03-worker-sigkill-after-actuation-journal-lost",
        loop,
        [make_request()],
        clock,
        [primary],
    )


def _b_provider_disappears(seed: int, inject: bool, *, at: str, scenario_id: str) -> Built:
    faults = [("provider_unavailable", 1)] * 4 if inject else []
    primary = ScriptedProvider(
        transport="fake:primary",
        claim_faults=faults if at == "claim" else [],
        execute_faults=faults if at == "execute" else [],
        effect=ok_effect(),
    )
    backup = ScriptedProvider(transport="fake:backup", effect=ok_effect())
    loop, clock = make_loop([primary, backup])
    request = make_request()

    def post(results: list[Any]) -> None:
        receipt = results[0].receipt
        assert receipt is not None
        assert (
            receipt.provider["transport"] == "fake:backup"
        ), f"expected substitution to backup, got {receipt.provider['transport']}"

    return Built(scenario_id, loop, [request], clock, [primary, backup], post=post)


def _b_provider_disappears_mid_claim(seed: int, inject: bool) -> Built:
    return _b_provider_disappears(
        seed, inject, at="claim", scenario_id="L7-F04-provider-disappears-mid-claim"
    )


def _b_provider_disappears_mid_execution(seed: int, inject: bool) -> Built:
    return _b_provider_disappears(
        seed, inject, at="execute", scenario_id="L7-F05-provider-disappears-mid-execution"
    )


def _b_partition_transient(seed: int, inject: bool) -> Built:
    primary = ScriptedProvider(
        claim_faults=[("network_partition", 2)] if inject else [],
        effect=ok_effect(),
    )
    loop, clock = make_loop([primary])
    return Built(
        "L7-F06-network-partition-transient", loop, [make_request()], clock, [primary]
    )


def _b_partition_persistent(seed: int, inject: bool) -> Built:
    primary = ScriptedProvider(
        claim_faults=[("network_partition", 1)] * 50 if inject else [],
        effect=ok_effect(),
    )
    loop, clock = make_loop([primary])
    return Built(
        "L7-F07-network-partition-persistent", loop, [make_request()], clock, [primary]
    )


def _b_delayed_within(seed: int, inject: bool) -> Built:
    primary = ScriptedProvider(
        claim_faults=[("delayed", 5)] if inject else [],
        effect=ok_effect(),
    )
    loop, clock = make_loop([primary])
    return Built(
        "L7-F08-delayed-response-within-deadline",
        loop,
        [make_request()],
        clock,
        [primary],
        post=lambda results: (clock.tick >= 5)
        or (_ for _ in ()).throw(AssertionError(f"backoff did not advance clock: {clock.tick}")),
    )


def _b_delayed_beyond(seed: int, inject: bool) -> Built:
    primary = ScriptedProvider(
        claim_faults=[("delayed", 5)] if inject else [],
        effect=ok_effect(),
    )
    loop, clock = make_loop([primary])
    request = make_request(resource_constraints=make_constraints(deadline_ticks=3))
    return Built(
        "L7-F09-delayed-response-beyond-deadline", loop, [request], clock, [primary]
    )


def _b_duplicate(seed: int, inject: bool) -> Built:
    primary = ScriptedProvider(effect=ok_effect())
    loop, clock = make_loop([primary])
    request = make_request(work_order="WO-L7-DUP")
    requests = [request] if not inject else [request, request]
    return Built("L7-F10-duplicate-work-order", loop, requests, clock, [primary])


def _b_lost_ack(seed: int, inject: bool, *, durable: bool, scenario_id: str) -> Built:
    primary = ScriptedProvider(
        ack_faults=[("lost_ack",)] if inject else [],
        journal_lost=not durable,
        effect=ok_effect(),
    )
    loop, clock = make_loop([primary])
    return Built(scenario_id, loop, [make_request()], clock, [primary])


def _b_lost_ack_durable(seed: int, inject: bool) -> Built:
    return _b_lost_ack(
        seed, inject, durable=True, scenario_id="L7-F11-lost-ack-durable-receipt"
    )


def _b_lost_ack_no_durable(seed: int, inject: bool) -> Built:
    return _b_lost_ack(
        seed, inject, durable=False, scenario_id="L7-F12-lost-ack-no-durable-receipt"
    )


def _b_stale_sha(seed: int, inject: bool) -> Built:
    primary = ScriptedProvider(world={"gymact": SHA_B if inject else SHA_A}, effect=ok_effect(SHA_B if inject else SHA_A))
    loop, clock = make_loop([primary])
    request = make_request(subject=SubjectRef(repo="gymact", sha=SHA_A))
    return Built("L7-F13-stale-subject-sha", loop, [request], clock, [primary])


def _moving_provider(*, every_execute: bool, once: bool) -> ScriptedProvider:
    def move_first(provider: ScriptedProvider) -> None:
        provider.world["gymact"] = SHA_B

    def move_every(provider: ScriptedProvider) -> None:
        current = provider.world["gymact"]
        provider.world["gymact"] = SHA_B if current == SHA_A else SHA_C

    return ScriptedProvider(
        on_execute=move_every if every_execute else move_first,
        effect=ok_effect(),
    )


def _b_moving_once(seed: int, inject: bool) -> Built:
    primary = _moving_provider(once=True, every_execute=False) if inject else ScriptedProvider(effect=ok_effect())
    loop, clock = make_loop([primary])
    return Built("L7-F14-moving-subject-single-move", loop, [make_request()], clock, [primary])


def _b_moving_beyond(seed: int, inject: bool) -> Built:
    primary = _moving_provider(every_execute=True, once=False) if inject else ScriptedProvider(effect=ok_effect())
    loop, clock = make_loop([primary])
    request = make_request(resource_constraints=make_constraints(max_subject_moves=1))
    return Built("L7-F15-moving-subject-beyond-budget", loop, [request], clock, [primary])


def _b_concurrent_conflict(seed: int, inject: bool) -> Built:
    # a concurrent writer advances the world during BOTH attempts
    primary = _moving_provider(every_execute=True, once=False) if inject else ScriptedProvider(effect=ok_effect())
    loop, clock = make_loop([primary])
    request = make_request(resource_constraints=make_constraints(max_subject_moves=1))
    return Built("L7-F16-concurrent-conflicting-changes", loop, [request], clock, [primary])


def _b_verifier_hard(seed: int, inject: bool) -> Built:
    verifier = (
        FakeVerifier([(False, "effect contradicts acceptance criteria")])
        if inject
        else FakeVerifier()
    )
    primary = ScriptedProvider(effect=ok_effect())
    loop, clock = make_loop([primary], verifier=verifier)
    return Built("L7-F17-verifier-failing-hard", loop, [make_request()], clock, [primary])


def _b_verifier_flaky(seed: int, inject: bool) -> Built:
    k = random.Random(seed).randint(1, 3)  # deterministic per seed
    verifier = (
        FakeVerifier([(False, "transient verification noise")] * k + [(True, "ok")])
        if inject
        else FakeVerifier()
    )
    primary = ScriptedProvider(effect=ok_effect())
    loop, clock = make_loop([primary], verifier=verifier)
    return Built("L7-F18-verifier-flaky-recovers", loop, [make_request()], clock, [primary])


def _b_invalid_authority(seed: int, inject: bool) -> Built:
    registry = FakeRegistry(valid=False) if inject else FakeRegistry(valid=True)
    primary = ScriptedProvider(effect=ok_effect())
    loop, clock = make_loop([primary], registry=registry)
    return Built("L7-F19-invalid-authority", loop, [make_request()], clock, [primary])


def _b_expired_credential(seed: int, inject: bool) -> Built:
    clock = VirtualClock()
    clock.tick = 10
    authority = (
        make_authority(expires_at_tick=5) if inject else make_authority(expires_at_tick=None)
    )
    primary = ScriptedProvider(effect=ok_effect())
    loop = AutonomousLoop(
        [primary],
        FakeVerifier(),
        FakeRegistry(),
        FakeProbe(),
        clock=clock.now,
        advance=clock.advance,
    )
    request = make_request(authority=authority)
    return Built("L7-F20-expired-credential", loop, [request], clock, [primary])


def _b_generator_drift(seed: int, inject: bool) -> Built:
    drifted = dict(ok_effect())
    drifted["effect_digest"] = "ff" * 8  # rendered output diverges from ontology
    verifier = (
        FakeVerifier([(False, "generator drift: effect digest disagrees with ontology render")])
        if inject
        else FakeVerifier()
    )
    primary = ScriptedProvider(effect=drifted if inject else ok_effect())
    loop, clock = make_loop([primary], verifier=verifier)
    return Built("L7-F21-generator-drift", loop, [make_request()], clock, [primary])


def _b_disk_pressure(seed: int, inject: bool) -> Built:
    probe = FakeProbe(disk_mb=100) if inject else FakeProbe()
    primary = ScriptedProvider(effect=ok_effect())
    loop, clock = make_loop([primary], probe=probe)
    return Built("L7-F22-disk-pressure", loop, [make_request()], clock, [primary])


def _b_cpu_pressure(seed: int, inject: bool) -> Built:
    probe = FakeProbe(cpu_cores=0.5) if inject else FakeProbe()
    primary = ScriptedProvider(effect=ok_effect())
    loop, clock = make_loop([primary], probe=probe)
    return Built("L7-F23-cpu-pressure", loop, [make_request()], clock, [primary])


def _b_rate_limit(seed: int, inject: bool) -> Built:
    rng = random.Random(seed)
    r1, r2 = rng.choice([1, 2, 3]), rng.choice([1, 2, 3])
    primary = ScriptedProvider(
        claim_faults=[("rate_limit", r1), ("rate_limit", r2)] if inject else [],
        effect=ok_effect(),
    )
    loop, clock = make_loop([primary])
    return Built(
        "L7-F24-rate-limit-429-1302",
        loop,
        [make_request()],
        clock,
        [primary],
        post=lambda results: (clock.tick > 0)
        or (_ for _ in ()).throw(AssertionError("rate-limit backoff did not advance clock")),
    )


def _b_dependency_outage(seed: int, inject: bool) -> Built:
    primary = ScriptedProvider(availability=not inject, effect=ok_effect())
    loop, clock = make_loop([primary])
    return Built("L7-F25-dependency-outage-all-providers", loop, [make_request()], clock, [primary])


def _b_impossible(seed: int, inject: bool) -> Built:
    primary = ScriptedProvider(effect=ok_effect())
    loop, clock = make_loop([primary])
    request = make_request(
        capability_requirements=["exec", "time_travel"] if inject else ["exec"]
    )
    return Built("L7-F26-impossible-objective", loop, [request], clock, [primary])


def _b_silent_mutation(seed: int, inject: bool, *, persistent: bool, scenario_id: str) -> Built:
    provider = ScriptedProvider(world={"gymact": SHA_A}, effect=ok_effect())
    fired = {"count": 0}

    def on_verify() -> None:
        if inject and (persistent or fired["count"] == 0):
            fired["count"] += 1
            provider.world["gymact"] = (
                SHA_B if provider.world["gymact"] == SHA_A else SHA_C
            )

    verifier = FakeVerifier(on_verify=on_verify)
    loop, clock = make_loop([provider], verifier=verifier)
    request = make_request(
        resource_constraints=make_constraints(max_subject_moves=1 if persistent else 2)
    )
    return Built(scenario_id, loop, [request], clock, [provider])


def _b_silent_once(seed: int, inject: bool) -> Built:
    return _b_silent_mutation(
        seed, inject, persistent=False, scenario_id="L7-F27-silent-external-state-mutation"
    )


def _b_silent_persistent(seed: int, inject: bool) -> Built:
    return _b_silent_mutation(
        seed, inject, persistent=True, scenario_id="L7-F28-silent-external-mutation-persistent"
    )


class StageWorldProvider:
    """lifegym-sim: a long-horizon multi-stage world. The committed subject
    digest covers HIDDEN STATE ONLY (stage progress is provider-journal work,
    not a subject move). The fault: entering stage 2 SILENTLY mutates hidden
    state -- no event, no announcement; the loop must catch it via the claim
    pin. lifegym checkout is ABSENT (BLOCKED_INFORMATION); this simulation
    runs inside the gymact harness."""

    transport = "fake:lifegym-sim"
    capabilities = ["exec", "long_horizon"]
    authority_ceiling = "DO"
    availability = True
    cost = 0.0
    concurrency = 1
    receipt_protocol = "fake+journal"

    def __init__(self, mutate_at_stage: int | None = 2, stages: int = 3):
        self.stages = stages
        self.mutate_at_stage = mutate_at_stage
        self.stage = 0
        self.hidden_state = "clean"
        self.claim_calls = 0
        self.execute_calls = 0
        self.stage_executions = 0
        self.journal: dict[str, dict[str, Any]] = {}

    def _sha(self) -> str:
        return digest({"hidden": self.hidden_state})

    def current_subject_sha(self, repo: str) -> str:
        return self._sha()

    def resolve_subject(self, repo: str) -> SubjectRef:
        return SubjectRef(repo=repo, sha=self._sha())

    def claim(self, request: ExecutionRequest) -> ClaimPin:
        self.claim_calls += 1
        return ClaimPin(
            provider_execution_id=f"lifegym-sim/{request.work_order}/{self.claim_calls}",
            pinned_subject_sha=self._sha(),
        )

    def execute(self, request: ExecutionRequest, provider_execution_id: str) -> dict[str, Any]:
        self.execute_calls += 1
        while self.stage < self.stages:
            self.stage += 1
            self.stage_executions += 1
            if self.stage == self.mutate_at_stage:
                self.hidden_state = "silently-mutated"  # no event, no notice
        fragment = {
            "effect_digest": digest({"stage": self.stage, "hidden": self.hidden_state}),
            "subject_after_sha": self._sha(),
            "actuation_count": 1,
            "consequence": {"stages_completed": self.stage, "world": "lifegym-sim"},
        }
        self.journal[provider_execution_id] = fragment
        return fragment

    def fetch_receipt(self, provider_execution_id: str) -> dict[str, Any] | None:
        return self.journal.get(provider_execution_id)

    def ack(self, receipt: ExecutionReceipt) -> None:
        return None


def _b_lifegym_multistage(seed: int, inject: bool) -> Built:
    world = StageWorldProvider(mutate_at_stage=2 if inject else None)

    class StageVerifier:
        def verify(
            self,
            subject_after: SubjectRef,
            effect_digest: str,
            request: ExecutionRequest,
        ) -> tuple[bool, str]:
            if world.stage >= world.stages:
                return True, f"stage {world.stage}/{world.stages} complete"
            return False, f"stage {world.stage}/{world.stages} incomplete"

    loop, clock = make_loop([world], verifier=StageVerifier())  # type: ignore[arg-type]
    request = make_request(
        work_order="WO-L7-LIFEGYM-001",
        capability_requirements=["exec", "long_horizon"],
        subject=SubjectRef(repo="lifegym-sim", sha=digest({"hidden": "clean"})),
    )

    def post(results: list[Any]) -> None:
        assert world.stage_executions >= 3, f"long horizon violated: {world.stage_executions}"
        assert world.claim_calls >= 2, f"multi-claim violated: {world.claim_calls}"

    return Built("L7-F31-lifegym-long-horizon-silent-stage-mutation", loop, [request], clock, [world], post=post)  # type: ignore[list-item]


BUILDERS: dict[str, Callable[[int, bool], Built]] = {
    "L7-F01-worker-sigkill-before-actuation": _b_crash_before,
    "L7-F02-worker-sigkill-after-actuation-journal-present": _b_crash_after_journal,
    "L7-F03-worker-sigkill-after-actuation-journal-lost": _b_crash_after_journal_lost,
    "L7-F04-provider-disappears-mid-claim": _b_provider_disappears_mid_claim,
    "L7-F05-provider-disappears-mid-execution": _b_provider_disappears_mid_execution,
    "L7-F06-network-partition-transient": _b_partition_transient,
    "L7-F07-network-partition-persistent": _b_partition_persistent,
    "L7-F08-delayed-response-within-deadline": _b_delayed_within,
    "L7-F09-delayed-response-beyond-deadline": _b_delayed_beyond,
    "L7-F10-duplicate-work-order": _b_duplicate,
    "L7-F11-lost-ack-durable-receipt": _b_lost_ack_durable,
    "L7-F12-lost-ack-no-durable-receipt": _b_lost_ack_no_durable,
    "L7-F13-stale-subject-sha": _b_stale_sha,
    "L7-F14-moving-subject-single-move": _b_moving_once,
    "L7-F15-moving-subject-beyond-budget": _b_moving_beyond,
    "L7-F16-concurrent-conflicting-changes": _b_concurrent_conflict,
    "L7-F17-verifier-failing-hard": _b_verifier_hard,
    "L7-F18-verifier-flaky-recovers": _b_verifier_flaky,
    "L7-F19-invalid-authority": _b_invalid_authority,
    "L7-F20-expired-credential": _b_expired_credential,
    "L7-F21-generator-drift": _b_generator_drift,
    "L7-F22-disk-pressure": _b_disk_pressure,
    "L7-F23-cpu-pressure": _b_cpu_pressure,
    "L7-F24-rate-limit-429-1302": _b_rate_limit,
    "L7-F25-dependency-outage-all-providers": _b_dependency_outage,
    "L7-F26-impossible-objective": _b_impossible,
    "L7-F27-silent-external-state-mutation": _b_silent_once,
    "L7-F28-silent-external-mutation-persistent": _b_silent_persistent,
    "L7-F31-lifegym-long-horizon-silent-stage-mutation": _b_lifegym_multistage,
}

# Guard scenarios (standing law / receipt law) raise instead of returning a
# LoopResult; they are exercised in test_illegal_outcomes.py, not here.
GUARD_SCENARIO_IDS = {"L7-F29-illegal-standing-transition-guard", "L7-F30-unnamespaced-receipt-ext-guard"}


# --------------------------------------------------------------------------- #
# Shared assertions
# --------------------------------------------------------------------------- #


def event_types(results: list[Any]) -> set[str]:
    return {event.event_type for result in results for event in result.events}


def assert_no_illegal_outcome(results: list[Any]) -> None:
    for result in results:
        assert result.outcome != "WaitForHumanToNotice", "ILLEGAL OUTCOME REACHED"
        assert result.asserted_illegal_outcome is None
        assert result.outcome in {"Recover", "Replan", "Substitute", "Refuse", "TypedBlock"}


def assert_required_events(results: list[Any], required: list[str]) -> None:
    observed = event_types(results)
    missing = set(required) - observed
    assert not missing, f"required fault-marker events missing: {sorted(missing)}; observed={sorted(observed)}"


def results_digest(results: list[Any]) -> str:
    return digest([[event.model_dump() for event in result.events] for result in results])


# --------------------------------------------------------------------------- #
# pytest fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="session")
def court() -> type["Court"]:
    """Shared court helpers, exposed as a fixture because --import-mode=importlib
    makes sibling ``import conftest`` from test modules impossible."""
    return Court


class Court:
    BUILDERS = BUILDERS
    GUARD_SCENARIO_IDS = GUARD_SCENARIO_IDS
    COURT_DIR = COURT_DIR
    load_manifest = staticmethod(load_manifest)
    assert_required_events = staticmethod(assert_required_events)
    assert_no_illegal_outcome = staticmethod(assert_no_illegal_outcome)
    event_types = staticmethod(event_types)
    results_digest = staticmethod(results_digest)


@pytest.fixture(scope="session")
def manifest() -> dict[str, Any]:
    data = load_manifest()
    scenarios = data["scenarios"]
    assert len(scenarios) >= 21, f"corpus too small: {len(scenarios)}"
    for scenario in scenarios:
        for key in (
            "id",
            "seeds",
            "fault_injection_point",
            "expected_legal_outcomes",
            "illegal_outcome_assertion",
            "required_ocel_events",
        ):
            assert key in scenario, f"{scenario.get('id')}: missing {key}"
        assert scenario["illegal_outcome_assertion"]
        assert set(scenario["expected_legal_outcomes"]) <= {
            "Recover",
            "Replan",
            "Substitute",
            "Refuse",
            "TypedBlock",
        }
    return data


def pytest_generate_tests(metafunc: Any) -> None:
    """Generate (scenario, seed) pairs from the manifest for every test that
    declares them; guard scenarios are excluded (they raise rather than
    return LoopResults and are exercised in test_illegal_outcomes.py)."""
    if {"scenario", "seed"} <= set(metafunc.fixturenames):
        pairs: list[tuple[dict[str, Any], int]] = []
        for scenario in load_manifest()["scenarios"]:
            if scenario["id"] in GUARD_SCENARIO_IDS:
                continue
            for seed in scenario["seeds"]:
                pairs.append((scenario, seed))
        metafunc.parametrize(
            "scenario,seed",
            pairs,
            ids=[f"{scenario['id']}(seed={seed})" for scenario, seed in pairs],
        )
