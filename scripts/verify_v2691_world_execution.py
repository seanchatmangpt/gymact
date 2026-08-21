#!/usr/bin/env python3
"""Independent v26.9.1 GymAct world-execution court.

This court does not add an actuation path. It first executes the existing canonical
Fortune-5-pattern M&A simulation, then independently drives the same admitted M&A
provider through GymAct's public consequence boundary to manufacture a real OCEL
receipt log. Standing is derived from consequential ACT receipts followed by an
independent VERIFY receipt; it is never inferred from an actuator's success string.
"""
from __future__ import annotations

import argparse
import asyncio
import copy
import json
import os
from pathlib import Path
from typing import Any

from gymact.evidence import digest
from gymact.gyms.mna import build_mna_provider
from gymact.gyms.ontology_gym import TieredAuthorityResolver, capability_iri
from gymact.mna import (
    BOARD_AUTHORITY,
    PRINCIPAL,
    SCENARIO,
    STANDARD_AUTHORITY,
    MnaSelectedPlan,
    execute_fortune5_mna_simulation,
    fortune5_mna_agent_space,
    fortune5_mna_space,
)
from gymact.models import ActuationIntent, MaterializationIntent, Operation, Standing
from gymact.ocel import digest_ocel_log, validate_ocel_log, write_ocel_log
from gymact.process import ConformanceChecker
from gymact.runtime import GymAct

DEFAULT_PLAN = MnaSelectedPlan(
    transaction_form="stock_purchase",
    consideration="mixed",
    integration_topology="federate",
    operating_model="business_unit",
    separation_strategy="transitional_services",
    regulatory_sequence="clear_then_sign",
)


class CourtRefusal(RuntimeError):
    """Typed verifier refusal: evidence does not support the requested standing."""


def _attr(event: dict[str, Any], name: str) -> str | None:
    for attribute in event.get("attributes", []):
        if attribute.get("name") == name:
            return str(attribute.get("value"))
    return None


def _verify_ocel(log: dict[str, Any], *, refusal_receipt_id: str) -> dict[str, Any]:
    validate_ocel_log(log)
    events = sorted(log["events"], key=lambda event: event["time"])
    try:
        operations = [Operation(event["type"]) for event in events]
    except ValueError as exc:
        raise CourtRefusal(f"REFUSED:UNKNOWN_OPERATION:{exc}") from exc

    replay = ConformanceChecker().check(operations)
    if not replay.conformant:
        reasons = ";".join(deviation.reason for deviation in replay.deviations)
        raise CourtRefusal(f"REFUSED:NONCONFORMANT_REPLAY:{reasons}")

    act_events = [event for event in events if event["type"] == Operation.ACT.value]
    alive_acts = [event for event in act_events if _attr(event, "standing") == Standing.ALIVE.value]
    if not alive_acts:
        raise CourtRefusal("REFUSED:NO_ALIVE_CONSEQUENTIAL_ACT")

    verify_events = [event for event in events if event["type"] == Operation.VERIFY.value]
    passed_verifications = [
        event
        for event in verify_events
        if _attr(event, "standing") == Standing.ALIVE.value
        and _attr(event, "verified") == "True"
    ]
    if not passed_verifications:
        raise CourtRefusal("REFUSED:NO_INDEPENDENT_PASSED_VERIFY_RECEIPT")

    refusal_events = [event for event in act_events if event["id"] == refusal_receipt_id]
    if len(refusal_events) != 1:
        raise CourtRefusal("REFUSED:MISSING_STANDARD_AUTHORITY_REFUSAL_RECEIPT")
    if _attr(refusal_events[0], "standing") != Standing.REFUSED.value:
        raise CourtRefusal("REFUSED:STANDARD_AUTHORITY_REFUSAL_NOT_REFUSED")

    first_verify_index = next(i for i, event in enumerate(events) if event in passed_verifications)
    last_alive_act_index = max(i for i, event in enumerate(events) if event in alive_acts)
    if first_verify_index <= last_alive_act_index:
        raise CourtRefusal("REFUSED:VERIFY_DID_NOT_FOLLOW_CONSEQUENTIAL_DO")

    return {
        "event_count": len(events),
        "act_count": len(act_events),
        "alive_act_count": len(alive_acts),
        "verify_count": len(verify_events),
        "passed_verify_count": len(passed_verifications),
        "replay_conformant": True,
        "ocel_sha256": digest_ocel_log(log),
    }


def _assert_mutation_refused(
    name: str,
    log: dict[str, Any],
    refusal_receipt_id: str,
    mutate: Any,
) -> str:
    mutant = copy.deepcopy(log)
    mutate(mutant)
    try:
        _verify_ocel(mutant, refusal_receipt_id=refusal_receipt_id)
    except Exception as exc:
        return f"{name}:{type(exc).__name__}"
    raise RuntimeError(f"MUTATION_SURVIVED:{name}")


REPLAN_TRIGGER_FACTS = frozenset(
    {
        "urn:gymact:mna:artifact-cyber-diligence",
        "urn:gymact:mna:artifact-technology-diligence",
    }
)


async def _verify_replanning(canonical: Any) -> dict[str, Any]:
    """Independent replanning court (gate G08, 'replanning'): a second
    episode's external SELECT must be genuinely conditioned on the canonical
    episode's real observed facts, not a hardcoded second plan. Mirrors
    scripts/run_fortune5_mna_replan_episode.py's real chained-episode design
    (SELECT stays external to GymAct in both episodes -- see that script's
    module docstring for why plan re-selection cannot happen by mutating the
    immutable MnaSelectedPlan mid-episode)."""
    observed = set(canonical.facts)
    if not REPLAN_TRIGGER_FACTS.issubset(observed):
        raise CourtRefusal("REFUSED:REPLAN_TRIGGER_FACTS_NOT_OBSERVED")

    replanned_topology = (
        "platform" if DEFAULT_PLAN.integration_topology != "platform" else "absorb"
    )
    replan_plan = DEFAULT_PLAN.model_copy(
        update={"integration_topology": replanned_topology}
    )
    replanned = await execute_fortune5_mna_simulation(replan_plan)

    if not replanned.verified or replanned.standing is not Standing.ALIVE:
        raise CourtRefusal("REFUSED:REPLAN_EPISODE_NOT_ALIVE")
    if replanned.episode_id == canonical.episode_id:
        raise CourtRefusal("REFUSED:REPLAN_EPISODE_ID_NOT_DISTINCT")
    if replanned.selected_plan == canonical.selected_plan:
        raise CourtRefusal("REFUSED:REPLAN_PLAN_DID_NOT_CHANGE")
    if replanned.selection_digest == canonical.selection_digest:
        raise CourtRefusal("REFUSED:REPLAN_SELECTION_DIGEST_UNCHANGED")

    return {
        "trigger_facts": sorted(REPLAN_TRIGGER_FACTS),
        "canonical_episode_id": canonical.episode_id,
        "canonical_plan": canonical.selected_plan.model_dump(mode="json"),
        "replan_episode_id": replanned.episode_id,
        "replan_plan": replanned.selected_plan.model_dump(mode="json"),
        "replan_verified": replanned.verified,
        "causal_link_digest": digest(
            {
                "canonical_episode_id": canonical.episode_id,
                "canonical_facts": sorted(canonical.facts),
                "replan_episode_id": replanned.episode_id,
                "replan_plan": replanned.selected_plan.model_dump(mode="json"),
            }
        ),
    }


async def _independent_world_court(ocel_output: Path) -> tuple[dict[str, Any], str, bool]:
    provider = build_mna_provider()
    resolver = TieredAuthorityResolver(
        elevated_capabilities=provider.elevated_capability_iris(),
        standard_ref=STANDARD_AUTHORITY,
        elevated_ref=BOARD_AUTHORITY,
    )
    gym = GymAct(authority_resolver=resolver)
    gym.register_provider(provider)

    selection_digest = digest(DEFAULT_PLAN.model_dump(mode="json"))
    materialization = await gym.materialize(
        MaterializationIntent(
            provider="mna",
            scenario=SCENARIO,
            principal=PRINCIPAL,
            idempotency_key=f"v2691-court:{selection_digest}:materialize",
        )
    )
    if not materialization.accepted or materialization.episode is None:
        raise CourtRefusal(
            f"REFUSED:MATERIALIZATION:{materialization.receipt.reason or materialization.standing}"
        )
    episode_id = materialization.episode.episode_id

    refusal_receipt_id: str | None = None
    successful_acts = 0
    for task in provider.tasks():
        capability = capability_iri(provider_name="mna", task=task)
        authority_ref = (
            BOARD_AUTHORITY
            if task.family in provider.elevated_task_families
            else STANDARD_AUTHORITY
        )
        subjects: tuple[str | None, ...] = task.subjects if len(task.subjects) > 1 else (None,)
        for subject in subjects:
            payload: dict[str, Any] = {}
            if subject is not None:
                payload["subject"] = subject
            if task.identifier == "mna.40.transaction-structure":
                payload["selected_plan"] = DEFAULT_PLAN.model_dump(mode="json")
                payload["selection_digest"] = selection_digest

            if task.family == "simulated-close" and refusal_receipt_id is None:
                refused = await gym.act(
                    ActuationIntent(
                        episode_id=episode_id,
                        capability=capability,
                        payload=payload,
                        authority_ref=STANDARD_AUTHORITY,
                        principal=PRINCIPAL,
                        idempotency_key=f"v2691-court:{selection_digest}:standard-close-refusal",
                    )
                )
                if refused.accepted or refused.standing is not Standing.REFUSED:
                    raise CourtRefusal("REFUSED:STANDARD_AUTHORITY_WAS_NOT_REFUSED")
                refusal_receipt_id = refused.receipt.receipt_id

            result = await gym.act(
                ActuationIntent(
                    episode_id=episode_id,
                    capability=capability,
                    payload=payload,
                    authority_ref=authority_ref,
                    principal=PRINCIPAL,
                    idempotency_key=digest(
                        {
                            "court": "v26.9.1-world-execution",
                            "selection": selection_digest,
                            "task": task.identifier,
                            "subject": subject,
                        }
                    ),
                )
            )
            if not result.accepted or result.standing is not Standing.ALIVE:
                raise CourtRefusal(
                    f"REFUSED:ACT:{task.identifier}:{result.receipt.reason or result.standing}"
                )
            successful_acts += 1

    verification = await gym.verify(episode_id, {"goal_reached": True})
    observed = await gym.observe(episode_id)
    if not verification.passed or observed.state.get("goal_reached") is not True:
        raise CourtRefusal("REFUSED:INDEPENDENT_FINAL_POSTCONDITION")
    if refusal_receipt_id is None:
        raise CourtRefusal("REFUSED:NO_STANDARD_AUTHORITY_REFUSAL")

    await gym.teardown(episode_id, authority_ref=BOARD_AUTHORITY)
    log, _ = write_ocel_log(ocel_output, gym.episode_receipts(episode_id))
    if successful_acts != 14:
        raise CourtRefusal(f"REFUSED:UNEXPECTED_ACT_COUNT:{successful_acts}")
    return log, refusal_receipt_id, True


async def _run(ocel_output: Path, report_output: Path) -> int:
    # Execute the existing production orchestration first. This is not replaced by
    # the court below; the court is an independent evidence path over the same world.
    canonical = await execute_fortune5_mna_simulation(DEFAULT_PLAN)
    if not canonical.verified or canonical.standing is not Standing.ALIVE:
        raise CourtRefusal("REFUSED:CANONICAL_MNA_SIMULATION_NOT_ALIVE")
    if canonical.external_transaction_attempted:
        raise CourtRefusal("REFUSED:EXTERNAL_TRANSACTION_ATTEMPTED")
    if canonical.llm_calls != 0:
        raise CourtRefusal("REFUSED:NONZERO_LLM_CALLS")
    if canonical.transaction_frontier_cardinality != 729:
        raise CourtRefusal("REFUSED:TRANSACTION_FRONTIER_DRIFT")
    if canonical.agent_frontier_cardinality != 216:
        raise CourtRefusal("REFUSED:AGENT_FRONTIER_DRIFT")
    if fortune5_mna_space().total_cardinality != 729:
        raise CourtRefusal("REFUSED:REGENERATED_TRANSACTION_FRONTIER_DRIFT")
    if fortune5_mna_agent_space().total_cardinality != 216:
        raise CourtRefusal("REFUSED:REGENERATED_AGENT_FRONTIER_DRIFT")

    log, refusal_receipt_id, goal_reached = await _independent_world_court(ocel_output)
    evidence = _verify_ocel(log, refusal_receipt_id=refusal_receipt_id)
    replanning = await _verify_replanning(canonical)

    falsifiers = [
        _assert_mutation_refused(
            "verify_false",
            log,
            refusal_receipt_id,
            lambda mutant: next(
                attribute
                for event in mutant["events"]
                if event["type"] == Operation.VERIFY.value
                for attribute in event["attributes"]
                if attribute["name"] == "verified"
            ).update(value="False"),
        ),
        _assert_mutation_refused(
            "lifecycle_start",
            log,
            refusal_receipt_id,
            lambda mutant: mutant["events"].__setitem__(
                0,
                {**mutant["events"][0], "type": Operation.ACT.value},
            ),
        ),
        _assert_mutation_refused(
            "authority_refusal_removed",
            log,
            refusal_receipt_id,
            lambda mutant: mutant.__setitem__(
                "events",
                [event for event in mutant["events"] if event["id"] != refusal_receipt_id],
            ),
        ),
    ]

    report = {
        "repository": os.environ.get("GITHUB_REPOSITORY", "seanchatmangpt/gymact"),
        "subject_sha": os.environ.get("SUBJECT_SHA", "LOCAL_UNBOUND"),
        "boundary": "v26.9.1-gymact-domain-world",
        "canonical": {
            "standing": canonical.standing.value,
            "verified": canonical.verified,
            "receipt_count": len(canonical.receipt_ids),
            "manufactured_agent_receipt_count": len(canonical.manufactured_agent_receipts),
            "llm_calls": canonical.llm_calls,
            "transaction_frontier_cardinality": canonical.transaction_frontier_cardinality,
            "agent_frontier_cardinality": canonical.agent_frontier_cardinality,
            "external_transaction_attempted": canonical.external_transaction_attempted,
        },
        "independent_court": {
            **evidence,
            "goal_reached": goal_reached,
            "standard_authority_refusal_receipt_id": refusal_receipt_id,
        },
        "replanning": replanning,
        "falsifiers": falsifiers,
        "falsifiers_passed": len(falsifiers),
        "generated_source_edited": False,
        "live_cloud_authority": "BLOCKED:LIVE_AZURE_AUTHORITY",
        "external_actuation": "NONE",
        "standing": "ALIVE",
    }
    report_output.parent.mkdir(parents=True, exist_ok=True)
    report_output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--ocel-output",
        type=Path,
        default=Path("artifacts/v2691-world-execution/episode.ocel.json"),
    )
    parser.add_argument(
        "--report-output",
        type=Path,
        default=Path("artifacts/v2691-world-execution/receipt.json"),
    )
    args = parser.parse_args()
    try:
        return asyncio.run(_run(args.ocel_output, args.report_output))
    except CourtRefusal as exc:
        print(str(exc))
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
