#!/usr/bin/env python3
"""Machine-readable regression benchmark for planned BRCE execution.

The thresholds are anti-collapse budgets suitable for shared CI runners. They
are not production SLO claims; retained deployment-hardware receipts should be
used to tighten them per environment.
"""

from __future__ import annotations

import asyncio
import json
from time import perf_counter

from gymact.action_contract import (
    ActionDefinition,
    ExecutionGrant,
    ExpectedEffect,
    SubjectRef,
    VerificationKind,
    VerificationStrategy,
    construct_prepared_action,
)
from gymact.authority import AllowListAuthorityResolver
from gymact.brce import BRCEBroker, BrokerRequest
from gymact.models import MaterializationIntent, Standing
from gymact.planning import PlanProvenance, bind_plan, execute_planned
from gymact.providers import MemoryProvider
from gymact.runtime import ProductionGymAct

AUTHORITY = "urn:gymact:benchmark:authority"
INCREMENT = "urn:gymact:memory:capability:increment"


def request(episode_id: str) -> BrokerRequest:
    effect = ExpectedEffect(predicate="count", parameters={"value": 1})
    action = ActionDefinition(
        semantic_id="urn:gymact:benchmark:increment",
        provider_ref="memory",
        capability_ref=INCREMENT,
        subject_type="schema:Thing",
        input_schema={"type": "object"},
        expected_effects=(effect,),
        verification=VerificationStrategy(
            kind=VerificationKind.EXACT_STATE,
            observer_ref="urn:gymact:benchmark:observer",
            expected={"count": 1},
        ),
    )
    subject = SubjectRef(
        semantic_id=f"urn:gymact:benchmark:episode:{episode_id}",
        provider_ref="memory",
    )
    prepared = construct_prepared_action(
        action,
        episode_id=episode_id,
        subject=subject,
        payload={"key": "count", "amount": 1},
        admission_digest="benchmark-admission",
        idempotency_key="benchmark-replay",
    )
    grant = ExecutionGrant(
        principal="urn:gymact:benchmark:principal",
        action_ref=action.semantic_id,
        subject=subject,
        capability_ref=action.capability_ref,
        authority_ref=AUTHORITY,
        policy_revision="benchmark-policy-v1",
        admitted_observation_ref="urn:gymact:benchmark:observation",
        intended_effects=action.expected_effects,
        nonce="benchmark-nonce",
    )
    return BrokerRequest(
        action=action,
        prepared=prepared,
        grant=grant,
        expected={"count": 1},
    )


def provenance() -> PlanProvenance:
    return PlanProvenance(
        plan_id="urn:gymact:benchmark:plan",
        plan_version="1",
        plan_step_id="increment",
        parent_step_ids=("observe",),
        required_authority_classes=("operator",),
    )


async def main_async() -> int:
    runtime = ProductionGymAct(
        authority_resolver=AllowListAuthorityResolver({AUTHORITY})
    )
    runtime.register_provider(MemoryProvider())
    materialized = await runtime.materialize(
        MaterializationIntent(
            provider="memory",
            config={"initial": {"count": 0}, "requires_authority": True},
            idempotency_key="benchmark-materialize",
        )
    )
    assert materialized.episode is not None
    broker = BRCEBroker(runtime)
    base_request = request(materialized.episode.episode_id)
    plan = provenance()

    bind_count = 50_000
    started = perf_counter()
    for _ in range(bind_count):
        bind_plan(base_request, plan)
    bind_seconds = perf_counter() - started

    planned = bind_plan(base_request, plan)
    started = perf_counter()
    first = await execute_planned(broker, planned)
    first_seconds = perf_counter() - started
    assert first.transition.standing is Standing.ALIVE

    replay_count = 2_000
    started = perf_counter()
    replays = [await execute_planned(broker, planned) for _ in range(replay_count)]
    replay_seconds = perf_counter() - started
    assert all(item.transition.standing is Standing.ALIVE for item in replays)
    assert (await runtime.observe(materialized.episode.episode_id)).state == {"count": 1}

    bind_rate = bind_count / max(bind_seconds, 1e-9)
    replay_rate = replay_count / max(replay_seconds, 1e-9)
    evidence_valid = runtime.verify_evidence_chain()
    metrics = {
        "schema": "urn:gymact:plan-provenance-benchmark:1",
        "bind": {
            "operations": bind_count,
            "seconds": bind_seconds,
            "operations_per_second": bind_rate,
        },
        "first_receipted_do": {
            "seconds": first_seconds,
            "milliseconds": first_seconds * 1000.0,
        },
        "exact_replay": {
            "operations": replay_count,
            "seconds": replay_seconds,
            "operations_per_second": replay_rate,
        },
        "evidence_chain_valid": evidence_valid,
    }
    failures: list[str] = []
    if bind_rate < 1_000:
        failures.append("PLAN_BIND_THROUGHPUT")
    if first_seconds > 2.0:
        failures.append("FIRST_RECEIPTED_DO_LATENCY")
    if replay_rate < 50:
        failures.append("EXACT_REPLAY_THROUGHPUT")
    if not evidence_valid:
        failures.append("EVIDENCE_CHAIN")
    metrics["standing"] = "ALIVE" if not failures else "BUILD_BROKEN"
    metrics["failures"] = failures
    print(json.dumps(metrics, sort_keys=True, separators=(",", ":")))
    return 0 if not failures else 1


def main() -> int:
    return asyncio.run(main_async())


if __name__ == "__main__":
    raise SystemExit(main())
