#!/usr/bin/env python3
"""Deterministic benchmark for the ALOOP execution kernel (gymact.execution_loop).

Runs the real ``AutonomousLoop`` over four episode classes with in-process
journaling providers and a virtual clock (no network, no sleep, no entropy):

* ``healthy``       claim -> execute -> verify -> receipt
* ``substitute``    primary disappears (max_retries+1 claim faults) -> backup
* ``crash_journal`` post-actuation SIGKILL, receipt rebuilt from the journal
* ``dedupe``        redelivery of a completed work order (zero actuation)

Two kinds of numbers are produced:

1. Structural counts (events, claims, actuations per episode). They are exact
   and deterministic; ``tests/explore_execution_loop/test_execution_loop_bench.py``
   pins them, so any kernel change that adds work per episode fails loudly.
2. Wall-clock timings (median / p95 ns per episode, episodes/s). These are
   machine-dependent and are recorded in the committed receipt; the test only
   enforces a generous ceiling (``CEILING_US_PER_EPISODE``).

Usage::

    uv run python scripts/bench_execution_loop.py [--episodes N] [--out PATH]
"""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import sys
import time
from pathlib import Path
from typing import Any

from gymact.evidence import digest
from gymact.execution_loop import (
    AuthorityGrant,
    AutonomousLoop,
    ClaimPin,
    ExecutionReceipt,
    ExecutionRequest,
    SubjectRef,
    TransportFault,
    WorkerCrashed,
)

SHA = "a" * 40
EFFECT_DIGEST = "de" * 8
CLASSES = ("healthy", "substitute", "crash_journal", "dedupe")
# Regression bounds. Wall time on a shared machine is noisy (a loaded host
# was measured at 30x the idle median), so the enforced bounds use the
# fastest sample of each class, which contention can only inflate:
#   * absolute: fastest episode of any class under CEILING_US_PER_EPISODE
#     (idle reference machine: 0.1-0.25 ms, i.e. >40x headroom);
#   * relative: fastest episode of each class at most MAX_RATIO_TO_HEALTHY
#     times the fastest healthy episode (reference: substitute ~2.1x), which
#     catches super-linear work in the fault paths independent of host speed.
CEILING_US_PER_EPISODE = 10_000
MAX_RATIO_TO_HEALTHY = 6.0


class _Clock:
    def __init__(self) -> None:
        self.tick = 0

    def now(self) -> int:
        return self.tick

    def advance(self, ticks: int) -> None:
        self.tick += ticks


class _Registry:
    def is_valid(self, grant: AuthorityGrant) -> bool:
        return True


class _Probe:
    def disk_mb_available(self) -> int:
        return 10_000

    def cpu_cores_available(self) -> float:
        return 8.0


class _Verifier:
    def verify(
        self, subject_after: SubjectRef, effect_digest: str, request: ExecutionRequest
    ) -> tuple[bool, str]:
        return effect_digest == EFFECT_DIGEST, "digest check"


class _Provider:
    capabilities = ("exec",)
    authority_ceiling = "DO"
    availability = True
    cost = 0.0
    concurrency = 1
    receipt_protocol = "journal"

    def __init__(
        self,
        transport: str,
        claim_faults: int = 0,
        crash_after: bool = False,
    ) -> None:
        self.transport = transport
        self.claim_faults = claim_faults
        self.crash_after = crash_after
        self.claims = 0
        self.actuations = 0
        self.journal: dict[str, dict[str, Any]] = {}

    def current_subject_sha(self, repo: str) -> str:
        return SHA

    def resolve_subject(self, repo: str) -> SubjectRef:
        return SubjectRef(repo=repo, sha=SHA)

    def claim(self, request: ExecutionRequest) -> ClaimPin:
        self.claims += 1
        if self.claim_faults:
            self.claim_faults -= 1
            raise TransportFault(kind="provider_unavailable")
        return ClaimPin(
            provider_execution_id=f"{self.transport}/{request.work_order}/{self.claims}",
            pinned_subject_sha=SHA,
        )

    def execute(self, request: ExecutionRequest, provider_execution_id: str) -> dict[str, Any]:
        self.actuations += 1
        effect = {"effect_digest": EFFECT_DIGEST, "subject_after_sha": SHA, "actuation_count": 1}
        self.journal[provider_execution_id] = effect
        if self.crash_after:
            self.crash_after = False
            raise WorkerCrashed(applied_before=True, injection_point="post-actuation")
        return dict(effect)

    def fetch_receipt(self, provider_execution_id: str) -> dict[str, Any] | None:
        return self.journal.get(provider_execution_id)

    def ack(self, receipt: ExecutionReceipt) -> None:
        return None


def _request(work_order: str) -> ExecutionRequest:
    return ExecutionRequest(
        work_order=work_order,
        capability_requirements=["exec"],
        subject=SubjectRef(repo="gymact", sha=SHA),
        authority=AuthorityGrant(ceiling="CONSTRUCT", grant="bench", actor="bench"),
        evidence_requirements=["verifier"],
    )


def run_episode(kind: str) -> dict[str, Any]:
    """Build and run one episode of ``kind``; return its structural counts."""
    clock = _Clock()
    if kind == "substitute":
        providers = [_Provider("primary", claim_faults=4), _Provider("backup")]
    elif kind == "crash_journal":
        providers = [_Provider("primary", crash_after=True)]
    else:
        providers = [_Provider("primary")]
    loop = AutonomousLoop(
        providers, _Verifier(), _Registry(), _Probe(), clock=clock.now, advance=clock.advance
    )
    request = _request(f"WO-BENCH-{kind}")
    if kind == "dedupe":
        loop.run(request)
    result = loop.run(request)
    return {
        "outcome": result.outcome,
        "standing": str(result.standing.value),
        "events": len(result.events),
        "claims": sum(p.claims for p in providers),
        "actuations": sum(p.actuations for p in providers),
        "result_actuation_count": result.actuation_count,
        "virtual_ticks": clock.tick,
    }


def structural_profile() -> dict[str, dict[str, Any]]:
    return {kind: run_episode(kind) for kind in CLASSES}


def time_class(kind: str, episodes: int) -> dict[str, float]:
    samples: list[int] = []
    for _ in range(episodes):
        start = time.perf_counter_ns()
        run_episode(kind)
        samples.append(time.perf_counter_ns() - start)
    samples.sort()
    median = statistics.median(samples)
    p95 = samples[min(len(samples) - 1, int(0.95 * len(samples)))]
    return {
        "episodes": episodes,
        "median_ns": float(median),
        "p95_ns": float(p95),
        "min_ns": float(samples[0]),
        "episodes_per_s": round(1e9 / median, 1),
    }


def violations(timings: dict[str, dict[str, float]]) -> dict[str, str]:
    """Bound violations over fastest samples (see the bound comment above)."""
    found: dict[str, str] = {}
    healthy = timings["healthy"]["min_ns"]
    for kind, timing in timings.items():
        if timing["min_ns"] > CEILING_US_PER_EPISODE * 1000:
            found[kind] = f"min_ns {timing['min_ns']} > ceiling"
        elif timing["min_ns"] > MAX_RATIO_TO_HEALTHY * healthy:
            found[kind] = f"min_ns {timing['min_ns']} > {MAX_RATIO_TO_HEALTHY}x healthy {healthy}"
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--episodes", type=int, default=2000)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    for kind in CLASSES:  # warm-up (imports, pydantic schema caches)
        run_episode(kind)
    structure = structural_profile()
    timings = {kind: time_class(kind, args.episodes) for kind in CLASSES}
    over = violations(timings)
    receipt = {
        "schema": "gymact/execution-loop-bench/1",
        "subject": "gymact.execution_loop.AutonomousLoop",
        "structural_profile": structure,
        "structural_digest": digest(structure),
        "timings": timings,
        "ceiling_us_per_episode": CEILING_US_PER_EPISODE,
        "max_ratio_to_healthy": MAX_RATIO_TO_HEALTHY,
        "violations": over,
        "within_ceiling": not over,
        "environment": {
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
            "machine": platform.machine(),
            "system": platform.system(),
        },
        "evidence_ceiling": "LOCAL_WALLCLOCK_SIMULATED_IN_PROCESS",
        "authority": "NONE",
    }
    text = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text)
    sys.stdout.write(text)
    return 0 if not over else 1


if __name__ == "__main__":
    raise SystemExit(main())
