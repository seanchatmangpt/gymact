#!/usr/bin/env python3
"""Real, live, end-to-end run of the new `gymact.epistemic_process_kernel`
EPK loop (cognitive operators from `gymact.epistemic_dspy`) against
sregym's real `misconfig_app_hotel_res` diagnosis scenario, on the REAL
live cluster only -- no mock, no `FakeSregymGym`.

This script is the provider-specific half of the split described in
`gymact.epistemic_process_kernel`'s own module docstring: it discovers
real capabilities, builds the real `Goal`/`Constraint`s, gathers real seed
facts via the same mechanical majority-vote outlier derivation already
proven in `dspy_sregym_agent.py` (reused, not reinvented), and then hands
everything to the generic `run_episode()`.

Usage:
    set -a; source ~/.env; set +a
    uv run python scripts/run_epk_sregym_diagnosis.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from gymact import AllowListAuthorityResolver, GymAct, MaterializationIntent
from gymact.dspy_sregym_agent import (
    DeploymentConfigSummary,
    _derive_deterministic_facts,
    _summarize_one_deployment,
)
from gymact.epistemic_dspy import Constraint, Fact, Goal
from gymact.epistemic_process_kernel import explain_episode, run_episode
from gymact.gyms.sregym import SregymVendorProvider
from gymact.limits import RuntimeLimits
from gymact.models import ActuationIntent

AUTHORITY = "urn:gymact:script:epk-sregym-diagnosis"
NAMESPACE = "hotel-reservation"


def _find_capability_iri(capabilities, binding: str) -> str:
    for cap in capabilities:
        if cap.binding == binding:
            return cap.iri
    raise LookupError(f"no real capability with binding {binding!r} on this episode")


async def _run_kubectl(gym: GymAct, episode_id: str, run_kubectl_iri: str, command: str) -> str:
    """Real, single kubectl call via the real kernel `gym.act()` -- the
    same actuation path `dspy_sregym_agent.py`'s own `_run_kubectl_raw`
    uses, duplicated minimally here rather than importing a private
    closure. Returns the real stdout text."""
    result = await gym.act(
        ActuationIntent(
            episode_id=episode_id,
            capability=run_kubectl_iri,
            payload={"command": command},
            authority_ref=AUTHORITY,
        )
    )
    effect = result.effect or {}
    blocks = effect.get("result_text", [])
    return blocks[0].get("text", "") if blocks else ""


async def _gather_seed_facts(gym: GymAct, episode_id: str, run_kubectl_iri: str) -> list[Fact]:
    """Real, mechanical seed-fact gathering -- the SAME real actuation +
    parsing already proven in `dspy_sregym_agent.py` (deployment configs
    -> majority-vote outlier detection across every structural field),
    reused here rather than reinvented, then converted from
    `gymact.epistemic_kernel.Fact` into `gymact.epistemic_dspy.Fact`
    (same id/subject/predicate/value shape, different provenance field
    name)."""
    names_text = await _run_kubectl(
        gym, episode_id, run_kubectl_iri,
        f"kubectl get deployments -n {NAMESPACE} -o jsonpath={{.items[*].metadata.name}}",
    )
    names = names_text.split()
    summaries: list[DeploymentConfigSummary] = []
    for name in names:
        text = await _run_kubectl(
            gym, episode_id, run_kubectl_iri,
            f"kubectl get deployment {name} -n {NAMESPACE} -o json",
        )
        if text.endswith("... [truncated]"):
            print(f"  (skipped {name}: truncated response)", file=sys.stderr)
            continue
        try:
            summaries.append(_summarize_one_deployment(json.loads(text)))
        except json.JSONDecodeError as exc:
            print(f"  (skipped {name}: unparseable: {exc})", file=sys.stderr)

    old_facts = _derive_deterministic_facts(summaries)
    return [
        Fact(
            id=f.id,
            subject=f.subject,
            predicate=f.predicate,
            value=f.value,
            source_observation_ids=[],
            derivation_ids=f.provenance,
        )
        for f in old_facts
    ]


async def main() -> None:
    if not os.environ.get("GROQ_API_KEY"):
        print("REFUSED: GROQ_API_KEY not set in this environment", file=sys.stderr)
        sys.exit(1)

    # See `scripts/run_dspy_sregym_diagnosis.py`'s own comment for why
    # 300s: the default 60s `materialize_timeout_s` fires falsely because
    # sregym's startup poll uses a blocking `time.sleep()` that never
    # yields to the event loop for real cancellation.
    gym = GymAct(
        authority_resolver=AllowListAuthorityResolver({AUTHORITY}),
        limits=RuntimeLimits(materialize_timeout_s=300.0),
    )
    gym.register_provider(SregymVendorProvider())

    materialization = await gym.materialize(
        MaterializationIntent(
            provider="sregym",
            config={
                "scenario": "misconfig_app_hotel_res",
                "wall_clock_timeout_s": 900,
                "verify_timeout_seconds": 300,
            },
            authority_ref=AUTHORITY,
        )
    )
    if not materialization.accepted:
        print(f"REFUSED at materialize: {materialization.receipt.reason}", file=sys.stderr)
        sys.exit(1)
    episode_id = materialization.episode.episode_id
    print(f"episode_id={episode_id}")

    # Real fix (same as `run_dspy_sregym_diagnosis.py`): wait for the real
    # conductor stage to reach "diagnosis" before acting -- materialize()
    # only waits for the HTTP/kubectl-mcp servers to accept connections,
    # not for fault-injection/workload setup to finish.
    print("waiting for real conductor stage to reach 'diagnosis' before diagnosing...")
    verification = await gym.verify(episode_id, {"stage": "diagnosis"})
    print(f"stage_ready={verification.passed} observed={verification.observed}")

    try:
        capabilities = gym.capabilities(episode_id)
        run_kubectl_iri = _find_capability_iri(capabilities, "run_kubectl")

        print("gathering real seed facts (deployment configs, majority-vote outliers)...")
        seed_facts = await _gather_seed_facts(gym, episode_id, run_kubectl_iri)
        print(f"  {len(seed_facts)} real seed facts")

        goal = Goal(
            id="goal:diagnose-and-mitigate",
            desired_predicates=[
                f"every deployment in namespace {NAMESPACE} is Running and healthy"
            ],
            prohibited_predicates=[],
            success_criteria=[
                "the real root cause is identified with grounded evidence and a "
                "concrete mitigation is applied"
            ],
        )
        constraints = [
            Constraint(
                id="constraint:grounding",
                expression="every hypothesis state and evidence link must be grounded "
                "in real, cited facts -- never asserted without a real fact_id",
                hard=True,
            )
        ]

        # Real, explicit, sregym-specific capability classification -- the
        # kernel no longer guesses this from naming conventions (see
        # `run_episode`'s own docstring for why that was wrong in
        # general). `run_kubectl` is real-authority `DO` but ALSO the
        # only way to gather new evidence, so it appears in both sets;
        # `submit_diagnosis`/`submit_mitigation` are DO-only (never
        # exposed to Discriminate -- consequential, BRCE-only).
        read_bindings = {
            "observe_cluster_state", "get_benchmark_status", "run_kubectl",
            "jaeger_get_services", "jaeger_get_operations", "jaeger_get_traces",
            "jaeger_get_dependency_graph", "loki_get_logs", "loki_get_labels",
            "loki_get_label_values", "prometheus_get_metrics", "prometheus_get_alerts",
        }
        do_bindings = read_bindings | {"submit_diagnosis", "submit_mitigation"}

        result = await run_episode(
            gym,
            episode_id,
            AUTHORITY,
            goal,
            constraints,
            seed_facts,
            read_capability_bindings=read_bindings,
            do_capability_bindings=do_bindings,
            judge_model_id="groq/openai/gpt-oss-120b",
            # Bumped from 3 -- real live runs today showed the mechanism
            # (Discriminate, uncommitted-after-investigation feedback,
            # rehypothesize) genuinely working, just running out of round
            # budget before converging on this real, multi-fault-looking
            # scenario (real, non-overlapping outliers exist across
            # image/command/env simultaneously). More real rounds gives
            # it more real chances to close, not a different mechanism.
            max_discriminate_rounds=6,
        )

        # Real tutor-explanation pass -- runs regardless of whether the
        # episode reached admission. A refused episode is real, checkable
        # evidence of what was tried and what remains open, not a failure
        # to hide; this is a senior-SRE-style mentoring narrative over
        # that real trace, never a fabricated root cause.
        lesson, lesson_why = await explain_episode(
            result, goal, judge_model_id="groq/openai/gpt-oss-120b"
        )
        print("\n=== senior-SRE walkthrough of this real episode ===")
        print(lesson)
        print("\n--- why these specific recommendations ---")
        print(lesson_why)

        print(f"\nadmitted={result.admitted}")
        print(f"admission_reason={result.admission_reason}")
        print(f"rounds_used={result.rounds_used}")
        print(f"diagnosis_submitted={result.diagnosis_submitted}")
        print(f"mitigation_submitted={result.mitigation_submitted}")
        print("\nhypotheses:")
        for h in result.hypotheses:
            print(f"  [{h.state}] {h.proposition}")
            print(f"      supporting={h.supporting_fact_ids!r}")
            print(f"      contradicting={h.contradicting_fact_ids!r}")
        if result.diagnosis is not None:
            print(f"\ndiagnosis.explanation={result.diagnosis.explanation!r}")
        if result.selected_plan is not None:
            print(f"selected_plan={result.selected_plan.name!r}")
            for step in result.selected_plan.steps:
                print(f"  step: {step.capability_id} params={step.parameters!r}")
        print(f"\n{len(result.steps)} real kernel steps:")
        for i, step in enumerate(result.steps, 1):
            print(f"  {i}. {step.kind}(payload={step.payload!r})")
            print(f"      result={step.result!r}")

        # Real [EVAL] log tail, same as `run_dspy_sregym_diagnosis.py` --
        # the only place the real grading verdict is ever visible.
        if result.diagnosis_submitted or result.mitigation_submitted:
            await asyncio.sleep(3.0)
            environment = gym._episodes[episode_id].environment
            full_log = environment.read_log_tail(n_chars=200_000)
            eval_markers = ("[EVAL]", "Cannot submit", "Succeed", "Failed")
            eval_lines = [
                line for line in full_log.splitlines() if any(m in line for m in eval_markers)
            ]
            print("\n--- real [EVAL]/submission-rejection lines found in the log ---")
            if eval_lines:
                for line in eval_lines:
                    print(line)
            else:
                print("(none found -- see full tail below)")
                print(full_log[-6000:])
    finally:
        teardown_receipt = await gym.teardown(episode_id, authority_ref=AUTHORITY)
        print(f"\nteardown standing={teardown_receipt.standing.value}")


if __name__ == "__main__":
    asyncio.run(main())
