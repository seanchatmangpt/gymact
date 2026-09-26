"""Autonomous execution loop kernel for ALOOP-style episodes (ExecutionRequest
-> ExecutionProvider -> ExecutionReceipt, with fault handling that never
terminates by waiting for a human).

This module exists because the ALOOP-ZCODE-DOGFOOD-001 episode needs a REAL,
executable control loop to attack: the loop assembles the repository's
existing constitutional primitives (``gymact.models.Standing`` for evidence
standing, ``gymact.evidence.digest`` for content addressing, OCEL 2.0 event
logs validated by ``gymact.ocel.validate_ocel_log`` against the vendored
official schema) into the episode contract:

* :class:`ExecutionRequest` — {work_order, capability_requirements, subject,
  authority, evidence_requirements, resource_constraints}
* :class:`ExecutionProvider` — {capabilities, transport, availability, cost,
  concurrency, authority_ceiling, receipt_protocol} plus claim/execute/ack
* :class:`ExecutionReceipt` — normalized {work_order_id, origin_authority,
  provider, provider_execution_id, subject_before, subject_after, commands,
  consequences, evidence, exit_status, timestamps, replay_binding} plus
  namespaced ``ext`` fields

LEGAL terminal outcomes are exactly :class:`LegalOutcome` (Recover, Replan,
Substitute, Refuse, TypedBlock). ``WaitForHumanToNotice`` is named only as
:class:`IllegalOutcome` so tests can prove it is unreachable: no code path in
this module can produce it, and every fault is answered by a bounded,
typed transition. Budget exhaustion is a TYPED BLOCK (with reason and broken
term), never an open-ended human escalation.

Every loop transition appends a real OCEL 2.0 event (``execution.start``,
``execution.claim``, ``actuation``, ``execution.crash``, ``failure.detect``,
``reconcile.retry``, ``reconcile.replan``, ``provider.replace``,
``verification``, ``receipt.emit``, ``refuse``, ``typed.block``) with the
episode's object vocabulary (subject, originAuthority, provider, worker,
receipt). ``loop_log(result)`` assembles the validated log.

All execution in the accompanying court is simulated-in-process (fakes
implementing :class:`ExecutionProvider`); nothing here actuates production.
"""

from __future__ import annotations

import random
from collections.abc import Callable, Iterable, Sequence
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from pydantic import Field

from gymact.evidence import digest
from gymact.models import FrozenModel, Standing

__all__ = [
    "LOOP_OCEL_EVENT_TYPES",
    "LOOP_OCEL_OBJECT_TYPES",
    "AuthorityGrant",
    "AutonomousLoop",
    "BrokenTerm",
    "EpisodeStanding",
    "ExecutionProvider",
    "ExecutionReceipt",
    "ExecutionRequest",
    "IllegalOutcome",
    "LegalOutcome",
    "LoopBudgetExceeded",
    "LoopResult",
    "OcelEvent",
    "ResourceConstraints",
    "SubjectRef",
    "WorkerCrashed",
    "loop_log",
]


class LegalOutcome(StrEnum):
    """The complete set of legal loop terminal outcomes."""

    RECOVER = "Recover"
    REPLAN = "Replan"
    SUBSTITUTE = "Substitute"
    REFUSE = "Refuse"
    TYPED_BLOCK = "TypedBlock"


class IllegalOutcome(StrEnum):
    """Outcomes that must be PROVEN unreachable for every scenario.

    A scenario whose only path forward is a human noticing means the loop
    failed. The kernel never produces this value; courts assert it cannot.
    """

    WAIT_FOR_HUMAN_TO_NOTICE = "WaitForHumanToNotice"


class EpisodeStanding(StrEnum):
    """Episode-level standings from the ALOOP contract.

    The transition ASSISTED -> AUTONOMOUS is forbidden; the loop starts at
    AUTONOMOUS (it never requests humans) and can only leave it for a typed
    blocked/failed standing. :meth:`EpisodeStanding.transition` enforces this.
    """

    AUTONOMOUS = "AUTONOMOUS"
    ASSISTED = "ASSISTED"
    BLOCKED_AUTHORITY = "BLOCKED_AUTHORITY"
    BLOCKED_INFORMATION = "BLOCKED_INFORMATION"
    FAILED = "FAILED"

    @staticmethod
    def transition(before: EpisodeStanding, after: EpisodeStanding) -> EpisodeStanding:
        if before is EpisodeStanding.ASSISTED and after is EpisodeStanding.AUTONOMOUS:
            raise LoopBudgetExceeded(
                "illegal standing transition ASSISTED -> AUTONOMOUS is forbidden"
            )
        return after


class BrokenTerm(StrEnum):
    """Typed terms carried by refusals and typed blocks (never bare strings)."""

    R_MISSING_AUTHORITY = "R_missing_authority"
    R_MISSING_IDENTITY = "R_missing_identity"
    R_MISSING_CONSEQUENCE = "R_missing_consequence"
    ADMISSION_VACUOUS = "admission_vacuous"
    MU_ON_O = "mu_on_O"
    RESOURCE_EXHAUSTED = "resource_exhausted"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    DEPENDENCY_OUTAGE = "dependency_outage"
    VERIFICATION_FAILED = "verification_failed"
    SUBJECT_UNSTABLE = "subject_unstable"
    SUBJECT_STALE = "subject_stale"
    IMPOSSIBLE_OBJECTIVE = "impossible_objective"
    TRANSPORT_PARTITION = "transport_partition"


class LoopBudgetExceeded(Exception):
    """Raised only by guards (e.g. illegal standing transition), never as an
    outcome: budget exhaustion inside the loop becomes a typed block."""


class TransportFault(Exception):
    """Provider-side fault surfaced through the claim/execute boundary."""

    def __init__(self, kind: str, retry_after_ticks: int = 1, applied_before: bool = False):
        super().__init__(f"transport fault {kind!r} applied_before={applied_before}")
        self.kind = kind
        self.retry_after_ticks = retry_after_ticks
        self.applied_before = applied_before


class WorkerCrashed(TransportFault):
    """Simulated SIGKILL of a worker mid-claim or mid-execution."""

    def __init__(self, applied_before: bool, injection_point: str):
        super().__init__(kind="worker_sigkill", retry_after_ticks=1, applied_before=applied_before)
        self.injection_point = injection_point


# --------------------------------------------------------------------------- #
# Contract models
# --------------------------------------------------------------------------- #


class SubjectRef(FrozenModel):
    repo: str
    sha: str


class ClaimPin(FrozenModel):
    """What a claim pins: the provider-side execution id AND the subject SHA
    the provider observed at claim time (the moving-subject check compares
    against this pin, not against the request's possibly-stale SHA)."""

    provider_execution_id: str
    pinned_subject_sha: str


class AuthorityGrant(FrozenModel):
    ceiling: str  # e.g. "SELECT" < "CONSTRUCT" < "DO"
    grant: str
    actor: str
    expires_at_tick: int | None = None  # None = never expires


class ResourceConstraints(FrozenModel):
    deadline_ticks: int = 200
    max_retries: int = 3
    max_provider_switches: int = 2
    max_subject_moves: int = 2
    disk_budget_mb: int = 512
    cpu_budget_cores: float = 2.0


class ExecutionRequest(FrozenModel):
    work_order: str
    capability_requirements: list[str]
    subject: SubjectRef
    authority: AuthorityGrant
    evidence_requirements: list[str]
    resource_constraints: ResourceConstraints = Field(default_factory=ResourceConstraints)
    idempotency_key: str = ""  # defaults to work_order

    def model_post_init(self, __context: Any) -> None:
        object.__setattr__(self, "idempotency_key", self.idempotency_key or self.work_order)


class ExecutionReceipt(FrozenModel):
    """Normalized receipt per the ALOOP contract; ``ext`` holds namespaced
    extensions only (keys are ``<namespace>.<field>`` strings)."""

    work_order_id: str
    origin_authority: dict[str, Any]
    provider: dict[str, Any]
    provider_execution_id: str
    subject_before: dict[str, Any]
    subject_after: dict[str, Any]
    commands: list[str]
    consequences: list[dict[str, Any]]
    evidence: list[dict[str, Any]]
    exit_status: str
    timestamps: dict[str, str]
    replay_binding: dict[str, Any]
    ext: dict[str, Any] = Field(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        for key in self.ext:
            if "." not in key:
                raise LoopBudgetExceeded(f"receipt ext key {key!r} is not namespaced")


class OcelEvent(FrozenModel):
    event_type: str
    tick: int
    attributes: dict[str, Any] = Field(default_factory=dict)
    objects: dict[str, str] = Field(default_factory=dict)  # object type -> object id


LOOP_OCEL_EVENT_TYPES: tuple[str, ...] = (
    "execution.start",
    "execution.claim",
    "actuation",
    "execution.crash",
    "failure.detect",
    "reconcile.retry",
    "reconcile.replan",
    "provider.replace",
    "verification",
    "receipt.emit",
    "refuse",
    "typed.block",
)

LOOP_OCEL_OBJECT_TYPES: tuple[str, ...] = (
    "subject",
    "originAuthority",
    "provider",
    "worker",
    "receipt",
)


# --------------------------------------------------------------------------- #
# Provider / collaborator protocols (implemented by in-process fakes in tests)
# --------------------------------------------------------------------------- #


@runtime_checkable
class ExecutionProvider(Protocol):
    """The episode contract's provider surface. Attributes are properties in
    fakes; the protocol only fixes names and types."""

    capabilities: Sequence[str]
    transport: str
    availability: bool
    cost: float
    concurrency: int
    authority_ceiling: str
    receipt_protocol: str

    def current_subject_sha(self, repo: str) -> str: ...

    def resolve_subject(self, repo: str) -> SubjectRef: ...

    def claim(self, request: ExecutionRequest) -> ClaimPin: ...

    def execute(self, request: ExecutionRequest, provider_execution_id: str) -> dict[str, Any]: ...

    def fetch_receipt(self, provider_execution_id: str) -> dict[str, Any] | None: ...

    def ack(self, receipt: ExecutionReceipt) -> None: ...


class ResourceProbe(Protocol):
    def disk_mb_available(self) -> int: ...

    def cpu_cores_available(self) -> float: ...


class Verifier(Protocol):
    def verify(
        self,
        subject_after: SubjectRef,
        effect_digest: str,
        request: ExecutionRequest,
    ) -> tuple[bool, str]: ...


class AuthorityRegistry(Protocol):
    def is_valid(self, grant: AuthorityGrant) -> bool: ...


_CEILING_ORDER = {"NONE": 0, "SELECT": 1, "CONSTRUCT": 2, "DO": 3}


def _ceiling_at_least(observed: str, required: str) -> bool:
    return _CEILING_ORDER.get(observed.upper(), 0) >= _CEILING_ORDER.get(required.upper(), 99)


# --------------------------------------------------------------------------- #
# Result
# --------------------------------------------------------------------------- #


class LoopResult(FrozenModel):
    outcome: str  # a LegalOutcome value; never IllegalOutcome
    standing: Standing
    episode_standing: EpisodeStanding
    receipt: ExecutionReceipt | None = None
    typed_reason: str | None = None
    broken_term: BrokenTerm | None = None
    actuation_count: int = 0
    events: list[OcelEvent] = Field(default_factory=list)

    @property
    def asserted_illegal_outcome(self) -> IllegalOutcome | None:
        """Always None by construction; exists so courts can name the illegal
        outcome explicitly when asserting it never occurred."""
        if self.outcome == IllegalOutcome.WAIT_FOR_HUMAN_TO_NOTICE.value:
            return IllegalOutcome.WAIT_FOR_HUMAN_TO_NOTICE
        return None


def loop_log(results: Iterable[LoopResult], *, seed: int = 0) -> dict[str, Any]:
    """Assemble real OCEL 2.0 logs from loop events, shaped exactly like
    ``gymact.ocel.receipts_to_ocel`` (validated against the vendored official
    schema by ``validate_ocel_log``). Deterministic given the events and seed:
    timestamps are derived from virtual ticks, ids from a stable counter, and
    the whole log digests identically across runs."""

    base = datetime(2026, 9, 25, tzinfo=UTC)
    events: list[dict[str, Any]] = []
    objects: dict[tuple[str, str], dict[str, Any]] = {}
    event_type_names: set[str] = set()

    for result in results:
        for index, event in enumerate(result.events):
            event_type_names.add(event.event_type)
            event_id = f"{event.event_type}-{index:04d}-{digest(event.model_dump())[:8]}"
            relationships = [
                {"objectId": object_id, "qualifier": object_type}
                for object_type, object_id in sorted(event.objects.items())
            ]
            events.append(
                {
                    "id": event_id,
                    "type": event.event_type,
                    "time": (base + timedelta(seconds=event.tick))
                    .isoformat()
                    .replace("+00:00", "Z"),
                    "attributes": [
                        {"name": name, "value": str(value)}
                        for name, value in sorted(event.attributes.items())
                    ]
                    + [{"name": "seed", "value": str(seed)}],
                    "relationships": relationships,
                }
            )
            for object_type, object_id in event.objects.items():
                objects[(object_type, object_id)] = {
                    "id": object_id,
                    "type": object_type,
                    "attributes": [],
                }

    event_types = [
        {
            "name": name,
            "attributes": [
                {"name": attr, "type": "string"}
                for attr in ("seed", "reason", "outcome", "standing", "provider")
            ],
        }
        for name in sorted(event_type_names)
    ]
    return {
        "eventTypes": event_types,
        "objectTypes": [
            {"name": object_type, "attributes": []}
            for object_type in sorted(obj[1] for obj in objects)
        ],
        "events": events,
        "objects": sorted(objects.values(), key=lambda o: (o["type"], o["id"])),
    }


# --------------------------------------------------------------------------- #
# The loop
# --------------------------------------------------------------------------- #


class AutonomousLoop:
    """Bounded autonomous execution of one :class:`ExecutionRequest` across a
    provider set. Every terminal is legal (Recover/Replan/Substitute/Refuse/
    TypedBlock) or an exception escapes; there is no human-notification path."""

    def __init__(
        self,
        providers: Sequence[ExecutionProvider],
        verifier: Verifier,
        authority_registry: AuthorityRegistry,
        resource_probe: ResourceProbe,
        *,
        clock: Callable[[], int] | None = None,
        advance: Callable[[int], None] | None = None,
        rng: random.Random | None = None,
    ):
        if not providers:
            raise LoopBudgetExceeded("AutonomousLoop requires at least one provider")
        self._providers = list(providers)
        self._verifier = verifier
        self._authority_registry = authority_registry
        self._resource_probe = resource_probe
        self._now = clock or (lambda: 0)
        self._advance = advance or (lambda ticks: None)
        self._rng = rng or random.Random(0)
        self._completed: dict[str, ExecutionReceipt] = {}
        self.events: list[OcelEvent] = []

    # -- event plumbing ----------------------------------------------------- #

    def _emit(
        self,
        event_type: str,
        request: ExecutionRequest,
        *,
        reason: str = "",
        outcome: str = "",
        standing: str = "",
        provider: str = "",
        extra: dict[str, Any] | None = None,
    ) -> None:
        attributes: dict[str, Any] = {"reason": reason}
        if outcome:
            attributes["outcome"] = outcome
        if standing:
            attributes["standing"] = standing
        if provider:
            attributes["provider"] = provider
        if extra:
            attributes.update(extra)
        self.events.append(
            OcelEvent(
                event_type=event_type,
                tick=self._now(),
                attributes=attributes,
                objects={
                    "subject": f"{request.subject.repo}@{request.subject.sha[:12]}",
                    "originAuthority": f"{request.authority.grant}:{request.authority.actor}",
                    "provider": provider or self._providers[0].transport,
                    "worker": request.work_order,
                },
            )
        )

    # -- gates --------------------------------------------------------------- #

    def _authority_gate(self, request: ExecutionRequest) -> LoopResult | None:
        """Cheapest high-information gate first: authority. Zero actuation."""
        if not self._authority_registry.is_valid(request.authority):
            self._emit(
                "refuse",
                request,
                reason="REFUSED_NO_AUTHORITY",
                outcome=LegalOutcome.REFUSE.value,
                standing=Standing.REFUSED.value,
            )
            return LoopResult(
                outcome=LegalOutcome.REFUSE.value,
                standing=Standing.REFUSED,
                episode_standing=EpisodeStanding.BLOCKED_AUTHORITY,
                typed_reason="REFUSED_NO_AUTHORITY",
                broken_term=BrokenTerm.R_MISSING_AUTHORITY,
                actuation_count=0,
                events=list(self.events),
            )
        expires = request.authority.expires_at_tick
        if expires is not None and expires <= self._now():
            self._emit(
                "refuse",
                request,
                reason="REFUSED_CREDENTIAL_EXPIRED",
                outcome=LegalOutcome.REFUSE.value,
                standing=Standing.REFUSED.value,
            )
            return LoopResult(
                outcome=LegalOutcome.REFUSE.value,
                standing=Standing.REFUSED,
                episode_standing=EpisodeStanding.BLOCKED_AUTHORITY,
                typed_reason="REFUSED_CREDENTIAL_EXPIRED",
                broken_term=BrokenTerm.R_MISSING_AUTHORITY,
                actuation_count=0,
                events=list(self.events),
            )
        return None

    def _feasibility_gate(self, request: ExecutionRequest) -> LoopResult | None:
        required = set(request.capability_requirements)
        for provider in self._providers:
            capable = required.issubset(set(provider.capabilities))
            ceiling_ok = _ceiling_at_least(provider.authority_ceiling, request.authority.ceiling)
            if capable and ceiling_ok:
                return None
        self._emit(
            "refuse",
            request,
            reason="REFUSED_IMPOSSIBLE_OBJECTIVE",
            outcome=LegalOutcome.REFUSE.value,
            standing=Standing.REFUSED.value,
        )
        return LoopResult(
            outcome=LegalOutcome.REFUSE.value,
            standing=Standing.REFUSED,
            episode_standing=EpisodeStanding.FAILED,
            typed_reason="REFUSED_IMPOSSIBLE_OBJECTIVE",
            broken_term=BrokenTerm.IMPOSSIBLE_OBJECTIVE,
            actuation_count=0,
            events=list(self.events),
        )

    def _resource_gate(self, request: ExecutionRequest) -> LoopResult | None:
        limits = request.resource_constraints
        disk = self._resource_probe.disk_mb_available()
        cpu = self._resource_probe.cpu_cores_available()
        reason = None
        broken = None
        if disk < limits.disk_budget_mb:
            reason = f"TYPED_BLOCK_RESOURCE_DISK available={disk} budget={limits.disk_budget_mb}"
            broken = BrokenTerm.RESOURCE_EXHAUSTED
        elif cpu < limits.cpu_budget_cores:
            reason = f"TYPED_BLOCK_RESOURCE_CPU available={cpu} budget={limits.cpu_budget_cores}"
            broken = BrokenTerm.RESOURCE_EXHAUSTED
        if reason is None or broken is None:
            return None
        self._emit(
            "typed.block",
            request,
            reason=reason,
            outcome=LegalOutcome.TYPED_BLOCK.value,
            standing=Standing.BLOCKED.value,
        )
        return LoopResult(
            outcome=LegalOutcome.TYPED_BLOCK.value,
            standing=Standing.BLOCKED,
            episode_standing=EpisodeStanding.BLOCKED_INFORMATION,
            typed_reason=reason,
            broken_term=broken,
            actuation_count=0,
            events=list(self.events),
        )

    # -- dedupe -------------------------------------------------------------- #

    def _dedupe_gate(self, request: ExecutionRequest) -> LoopResult | None:
        existing = self._completed.get(request.idempotency_key)
        if existing is None:
            return None
        self._emit(
            "reconcile.retry",
            request,
            reason="DUPLICATE_WORK_ORDER_DEDUPLICATED",
            outcome=LegalOutcome.RECOVER.value,
            standing=Standing.ALIVE.value,
            extra={"provider_execution_id": existing.provider_execution_id},
        )
        return LoopResult(
            outcome=LegalOutcome.RECOVER.value,
            standing=Standing.ALIVE,
            episode_standing=EpisodeStanding.AUTONOMOUS,
            receipt=existing,
            typed_reason=None,
            broken_term=None,
            actuation_count=0,  # a duplicate performs NO additional actuation
            events=list(self.events),
        )

    # -- main ---------------------------------------------------------------- #

    def run(self, request: ExecutionRequest) -> LoopResult:
        self.events = []
        for gate in (
            self._authority_gate,
            self._feasibility_gate,
            self._resource_gate,
            self._dedupe_gate,
        ):
            blocked = gate(request)
            if blocked is not None:
                return blocked

        self._emit("execution.start", request, reason="", standing=Standing.UNKNOWN.value)
        limits = request.resource_constraints
        current_subject = self._resolve_fresh(request)
        if isinstance(current_subject, LoopResult):
            return current_subject
        subject_before = current_subject

        switches = 0
        attempts = 0
        moves = 0
        provider_index = self._select_provider_index(request)
        if provider_index is None:
            return self._typed_block(
                request, "TYPED_BLOCK_DEPENDENCY_OUTAGE", BrokenTerm.DEPENDENCY_OUTAGE
            )
        faults_on_provider = 0

        effect: dict[str, Any] | None = None
        while True:
            if attempts > limits.max_retries or self._now() >= limits.deadline_ticks:
                return self._typed_block(
                    request, "TYPED_BLOCK_BUDGET_EXHAUSTED", BrokenTerm.PROVIDER_UNAVAILABLE
                )
            attempts += 1
            provider = self._providers[provider_index]
            try:
                pin = provider.claim(request)
            except TransportFault as fault:
                faults_on_provider += 1
                self._on_transport_fault(
                    request, fault, attempts, limits, provider=provider.transport
                )
                if faults_on_provider <= limits.max_retries:
                    # transient claim fault: bounded same-provider retry (Recover)
                    self._emit(
                        "reconcile.retry",
                        request,
                        reason=f"backoff {fault.retry_after_ticks} ticks after {fault.kind}",
                        outcome=LegalOutcome.RECOVER.value,
                        provider=provider.transport,
                    )
                    self._advance(fault.retry_after_ticks)
                    continue
                switched = self._next_capable_index(request, provider_index)
                if switched is None or switches >= limits.max_provider_switches:
                    return self._typed_block(
                        request, "TYPED_BLOCK_PROVIDER_UNAVAILABLE", BrokenTerm.PROVIDER_UNAVAILABLE
                    )
                switches += 1
                faults_on_provider = 0
                attempts = 0  # fresh retry budget on the substituted provider
                provider_index = switched
                self._emit(
                    "provider.replace",
                    request,
                    reason=f"provider.replace after {fault.kind}",
                    outcome=LegalOutcome.SUBSTITUTE.value,
                    provider=self._providers[provider_index].transport,
                )
                continue

            self._emit(
                "execution.claim",
                request,
                reason=(
                    f"claimed {pin.provider_execution_id} pinned sha={pin.pinned_subject_sha[:12]}"
                ),
                provider=provider.transport,
            )
            try:
                effect = provider.execute(request, pin.provider_execution_id)
            except WorkerCrashed as crash:
                self._emit(
                    "execution.crash",
                    request,
                    reason=f"worker SIGKILL at {crash.injection_point}",
                    provider=provider.transport,
                )
                self._emit(
                    "failure.detect",
                    request,
                    reason="lease/liveness loss detected",
                    provider=provider.transport,
                )
                if crash.applied_before:
                    # crash AFTER actuation BEFORE receipt: reconcile from the
                    # provider-side durable journal; never re-actuate.
                    fragment = provider.fetch_receipt(pin.provider_execution_id)
                    if fragment is None:
                        return self._typed_block(
                            request,
                            "TYPED_BLOCK_RECEIPT_LOST",
                            BrokenTerm.R_MISSING_CONSEQUENCE,
                        )
                    self._advance(1)
                    receipt = self._build_receipt(
                        request,
                        provider,
                        pin,
                        subject_before,
                        fragment,
                        outcome=LegalOutcome.RECOVER.value,
                    )
                    self._completed[request.idempotency_key] = receipt
                    self._emit(
                        "receipt.emit",
                        request,
                        reason="reconstructed from provider journal",
                        outcome=LegalOutcome.RECOVER.value,
                        standing=Standing.ALIVE.value,
                        provider=provider.transport,
                    )
                    return LoopResult(
                        outcome=LegalOutcome.RECOVER.value,
                        standing=Standing.ALIVE,
                        episode_standing=EpisodeStanding.AUTONOMOUS,
                        receipt=receipt,
                        actuation_count=1,  # exactly once, despite the crash
                        events=list(self.events),
                    )
                # crash BEFORE actuation: safe to retry in place.
                self._emit(
                    "reconcile.retry",
                    request,
                    reason="crash before actuation; retrying",
                    outcome=LegalOutcome.RECOVER.value,
                    provider=provider.transport,
                )
                self._advance(1)
                continue
            except TransportFault as fault:
                faults_on_provider += 1
                self._emit(
                    "failure.detect",
                    request,
                    reason=fault.kind,
                    provider=provider.transport,
                )
                if faults_on_provider > limits.max_retries:
                    # provider slot is persistently broken (e.g. dead worker
                    # state): substitute instead of burning the whole budget.
                    switched = self._next_capable_index(request, provider_index)
                    if switched is None or switches >= limits.max_provider_switches:
                        return self._typed_block(
                            request,
                            "TYPED_BLOCK_PROVIDER_UNAVAILABLE",
                            BrokenTerm.PROVIDER_UNAVAILABLE,
                        )
                    switches += 1
                    faults_on_provider = 0
                    attempts = 0  # fresh retry budget on the substituted provider
                    provider_index = switched
                    self._emit(
                        "provider.replace",
                        request,
                        reason=f"provider.replace after {fault.kind}",
                        outcome=LegalOutcome.SUBSTITUTE.value,
                        provider=self._providers[provider_index].transport,
                    )
                    continue
                self._emit(
                    "reconcile.retry",
                    request,
                    reason=f"backoff {fault.retry_after_ticks} ticks after {fault.kind}",
                    outcome=LegalOutcome.RECOVER.value,
                    provider=provider.transport,
                )
                self._advance(fault.retry_after_ticks)
                continue

            # moving-subject check: subject must not have moved under us.
            observed_sha = provider.current_subject_sha(request.subject.repo)
            if observed_sha != pin.pinned_subject_sha:
                moves += 1
                if moves > limits.max_subject_moves:
                    return self._typed_block(
                        request, "TYPED_BLOCK_MOVING_SUBJECT", BrokenTerm.SUBJECT_UNSTABLE
                    )
                self._emit(
                    "reconcile.replan",
                    request,
                    reason=(f"subject moved {pin.pinned_subject_sha[:12]}->{observed_sha[:12]}"),
                    outcome=LegalOutcome.REPLAN.value,
                    provider=provider.transport,
                )
                subject_before = SubjectRef(repo=request.subject.repo, sha=pin.pinned_subject_sha)
                current_subject = self._resolve_fresh(request)
                if isinstance(current_subject, LoopResult):
                    return current_subject
                continue

            # verification
            verified, why = self._verifier.verify(
                SubjectRef(repo=request.subject.repo, sha=observed_sha),
                str(effect.get("effect_digest", "")),
                request,
            )
            verify_retries = 0
            while not verified and verify_retries < limits.max_retries:
                verify_retries += 1
                self._emit(
                    "failure.detect",
                    request,
                    reason=f"verifier rejected: {why} (retry {verify_retries})",
                    provider=provider.transport,
                )
                self._advance(1)
                verified, why = self._verifier.verify(
                    SubjectRef(repo=request.subject.repo, sha=observed_sha),
                    str(effect.get("effect_digest", "")),
                    request,
                )
            self._emit(
                "verification",
                request,
                reason=why,
                standing=Standing.ALIVE.value if verified else Standing.BLOCKED.value,
                provider=provider.transport,
            )
            if not verified:
                return self._typed_block(
                    request,
                    f"TYPED_BLOCK_VERIFICATION_FAILED {why}",
                    BrokenTerm.VERIFICATION_FAILED,
                )

            # silent external mutation check between verify and receipt.
            post_sha = provider.current_subject_sha(request.subject.repo)
            if post_sha != observed_sha:
                moves += 1
                if moves > limits.max_subject_moves:
                    return self._typed_block(
                        request, "TYPED_BLOCK_SILENT_MUTATION", BrokenTerm.SUBJECT_STALE
                    )
                self._emit(
                    "reconcile.replan",
                    request,
                    reason="silent external state mutation detected post-verify",
                    outcome=LegalOutcome.REPLAN.value,
                    provider=provider.transport,
                )
                continue

            self._advance(1)
            receipt = self._build_receipt(
                request,
                provider,
                pin,
                subject_before,
                effect,
                outcome=LegalOutcome.RECOVER.value,
            )
            try:
                provider.ack(receipt)
            except TransportFault:
                # lost ACK: the receipt exists and is replayable by id; the
                # loop recovers it locally instead of re-executing.
                durable = provider.fetch_receipt(pin.provider_execution_id)
                reason = (
                    "ACK lost; receipt recovered via replay binding"
                    if durable is not None
                    else "ACK lost; receipt retained loop-side via replay binding"
                )
                self._emit(
                    "reconcile.retry",
                    request,
                    reason=reason,
                    outcome=LegalOutcome.RECOVER.value,
                    provider=provider.transport,
                )
            self._completed[request.idempotency_key] = receipt
            self._emit(
                "receipt.emit",
                request,
                reason="verified",
                outcome=LegalOutcome.RECOVER.value,
                standing=Standing.ALIVE.value,
                provider=provider.transport,
            )
            return LoopResult(
                outcome=LegalOutcome.RECOVER.value,
                standing=Standing.ALIVE,
                episode_standing=EpisodeStanding.AUTONOMOUS,
                receipt=receipt,
                actuation_count=int(effect.get("actuation_count", 1)),
                events=list(self.events),
            )

    # -- helpers ------------------------------------------------------------- #

    def _on_transport_fault(
        self,
        request: ExecutionRequest,
        fault: TransportFault,
        attempts: int,
        limits: ResourceConstraints,
        *,
        provider: str = "",
    ) -> None:
        """Shared fault reaction for rate-limit faults ([1302]/429 shape):
        exponential backoff on the virtual clock; purely an event + clock
        transition, never a human escalation."""
        if fault.kind == "rate_limit":
            self._advance(min(2**attempts, 8) * fault.retry_after_ticks)
        self._emit(
            "failure.detect",
            request,
            reason=f"{fault.kind} (backoff scheduled)",
            provider=provider,
        )

    def _resolve_fresh(self, request: ExecutionRequest) -> SubjectRef | LoopResult:
        """Stale-subject-SHA handling: re-resolve the subject; on failure,
        typed-block on INFORMATION (never a silent guess, never a human)."""
        provider = self._providers[0]
        try:
            fresh = provider.resolve_subject(request.subject.repo)
        except TransportFault as fault:
            self._emit("failure.detect", request, reason=fault.kind)
            return self._typed_block(
                request, "TYPED_BLOCK_SUBJECT_UNRESOLVABLE", BrokenTerm.R_MISSING_IDENTITY
            )
        if fresh.sha != request.subject.sha:
            self._emit(
                "reconcile.replan",
                request,
                reason=f"stale subject sha {request.subject.sha[:12]} -> {fresh.sha[:12]}",
                outcome=LegalOutcome.REPLAN.value,
            )
        return fresh

    def _select_provider_index(self, request: ExecutionRequest) -> int | None:
        return self._next_capable_index(request, start=-1)

    def _next_capable_index(self, request: ExecutionRequest, start: int) -> int | None:
        required = set(request.capability_requirements)
        for index in range(start + 1, len(self._providers)):
            provider = self._providers[index]
            if not provider.availability:
                continue  # dependency outage for this provider: try next
            if not required.issubset(set(provider.capabilities)):
                continue
            if not _ceiling_at_least(provider.authority_ceiling, request.authority.ceiling):
                continue
            return index
        return None

    def _typed_block(
        self, request: ExecutionRequest, reason: str, broken: BrokenTerm
    ) -> LoopResult:
        self._emit(
            "typed.block",
            request,
            reason=reason,
            outcome=LegalOutcome.TYPED_BLOCK.value,
            standing=Standing.BLOCKED.value,
        )
        return LoopResult(
            outcome=LegalOutcome.TYPED_BLOCK.value,
            standing=Standing.BLOCKED,
            episode_standing=EpisodeStanding.BLOCKED_INFORMATION,
            typed_reason=reason,
            broken_term=broken,
            actuation_count=0,
            events=list(self.events),
        )

    def _build_receipt(
        self,
        request: ExecutionRequest,
        provider: ExecutionProvider,
        pin: ClaimPin,
        subject_before: SubjectRef,
        effect: dict[str, Any],
        *,
        outcome: str,
    ) -> ExecutionReceipt:
        subject_after = SubjectRef(
            repo=request.subject.repo,
            sha=str(effect.get("subject_after_sha", subject_before.sha)),
        )
        ext: dict[str, Any] = {
            "aloup.outcome": outcome,
            "aloup.execution_class": "simulated-in-process",
            "aloup.ocel_digest": digest([event.model_dump() for event in self.events]),
        }
        return ExecutionReceipt(
            work_order_id=request.work_order,
            origin_authority=dict(request.authority.model_dump()),
            provider={
                "transport": provider.transport,
                "capabilities": list(provider.capabilities),
                "authority_ceiling": provider.authority_ceiling,
                "receipt_protocol": provider.receipt_protocol,
            },
            provider_execution_id=pin.provider_execution_id,
            exit_status="success" if outcome == LegalOutcome.RECOVER.value else outcome,
            subject_before=dict(subject_before.model_dump()),
            subject_after=dict(subject_after.model_dump()),
            commands=[f"execute({request.work_order}) via {provider.transport}"],
            consequences=[dict(effect.get("consequence", {}))],
            evidence=[
                {
                    "kind": "verifier",
                    "effect_digest": effect.get("effect_digest", ""),
                    "evidence_requirements": list(request.evidence_requirements),
                }
            ],
            timestamps={
                "emitted_at_tick": str(self._now()),
                "emitted_at": f"tick:{self._now()}",
            },
            replay_binding={
                "provider_execution_id": pin.provider_execution_id,
                "pinned_subject_sha": pin.pinned_subject_sha,
                "durable_location": f"{provider.receipt_protocol}://{provider.transport}/{pin.provider_execution_id}",
                "idempotency_key": request.idempotency_key,
            },
            ext=ext,
        )
