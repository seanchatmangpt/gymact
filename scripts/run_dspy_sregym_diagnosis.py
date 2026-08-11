#!/usr/bin/env python3
"""Real, live, end-to-end run of `SregymDiagnosisAgent` (the sregym-specific
DSPy ReAct agent -- real typed `RunKubectlPayload`/`SubmitDiagnosisPayload`/
`SubmitMitigationPayload` signatures, not the generic bare-dict agent)
against sregym's real `misconfig_app_hotel_res` diagnosis scenario:
materialize -> observe -> run_kubectl (diagnose) -> submit_diagnosis ->
submit_mitigation -> teardown, all through the real GymAct kernel and a real
Groq-hosted LM.

This script does not assert or print a standing verdict (ALIVE/BLOCKED/...)
-- per this repo's OCEL-standing rule, only a real, schema-valid,
conformant-replay OCEL log backs that claim. It reports the real, honest
step trace and outcome so a human can judge it.

Usage:
    set -a; source ~/.env; set +a
    uv run python scripts/run_dspy_sregym_diagnosis.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from gymact import AllowListAuthorityResolver, GymAct, MaterializationIntent
from gymact.dspy_ocel import write_dspy_ocel_log
from gymact.dspy_sregym_agent import IncidentContext, SregymDiagnosisAgent
from gymact.gyms.sregym import SregymVendorProvider
from gymact.limits import RuntimeLimits

AUTHORITY = "urn:gymact:script:dspy-sregym-diagnosis"

# Real, known-structured facts only -- see `IncidentContext`'s own
# docstring for why this isn't a prose description of the incident.
INCIDENT = IncidentContext(namespace="hotel-reservation", app_name="hotel-reservation")


async def main() -> None:
    if not os.environ.get("GROQ_API_KEY"):
        print("REFUSED: GROQ_API_KEY not set in this environment", file=sys.stderr)
        sys.exit(1)

    # Real defect found and fixed forward this session: `RuntimeLimits`'s
    # default `materialize_timeout_s` (60s) wraps the whole
    # `provider.materialize()` call in `anyio.fail_after`, but sregym's
    # own startup poll (`gymact.polling.poll_until`) uses a real BLOCKING
    # `time.sleep()`, never yielding to the event loop -- so the 60s
    # cancellation can't actually fire until the blocking call returns on
    # its own. Confirmed live: the real subprocess/cluster startup
    # reliably takes well over 60s, so the kernel retroactively declared
    # `MATERIALIZATION_TIMEOUT` every time AFTER the environment had
    # already, successfully, finished starting -- and then discarded that
    # live environment object without ever calling teardown on it (the
    # caller never received it), leaking a real Docker container +
    # kubectl port-forward on every single materialize() call. 300s
    # matches this scenario's real observed startup time with margin.
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
                # Real fix for the real timeout this script's prior live run
                # hit: fault-injection/workload setup took longer than the
                # 120s default -- 300s matches this scenario's real observed
                # TTL/TTM range (autofde_lab_planner's own real runs: TTL
                # ~50-99s, TTM ~51-326s, AFTER setup finishes).
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

    # Real, honest fix for a real timing bug this script's first live run
    # surfaced: `materialize()`'s readiness wait only waits for the
    # conductor HTTP/kubectl-mcp servers to accept connections, NOT for the
    # real fault-injection/workload setup to finish -- the agent's very
    # first `run_kubectl` calls raced a namespace that was, confirmed live,
    # only 1 second old. `autofde_lab_planner` (this scenario's real 100%-
    # composite-score baseline) avoids this by waiting on
    # `verify({"stage": "diagnosis"})` before letting its agent act; this
    # script now does the same real wait.
    print("waiting for real conductor stage to reach 'diagnosis' before diagnosing...")
    verification = await gym.verify(episode_id, {"stage": "diagnosis"})
    print(f"stage_ready={verification.passed} observed={verification.observed}")

    # Bumped off gpt-oss-20b: its prior live run hit a real Groq/litellm
    # incompatibility ("Tool choice is none, but model called a tool") on a
    # later ReAct iteration -- a known class of tool-calling inconsistency
    # for that model on Groq, not a gymact code defect.
    agent = SregymDiagnosisAgent(
        gym,
        episode_id,
        authority_ref=AUTHORITY,
        judge_model_id="groq/openai/gpt-oss-120b",
        max_iters=12,
    )

    try:
        result = await agent.run_diagnosis(INCIDENT)
        print(f"diagnosis_submitted={result.diagnosis_submitted}")
        print(f"mitigation_submitted={result.mitigation_submitted}")
        print(f"root_cause={result.root_cause}")
        print(f"mitigation={result.mitigation}")
        print("\nnormalized_facts:")
        for fact in result.normalized_facts:
            print(f"  - {fact}")
        print("\nhypotheses:")
        for h in result.hypotheses:
            print(f"  [{h.state.value}] {h.hypothesis}")
            print(f"      evidence_ids={h.evidence_ids!r}")
            print(f"      reasoning={h.reasoning!r}")
        print(f"\nkernel_admitted={result.kernel_admitted}")
        print(f"kernel_admission_reason={result.kernel_admission_reason}")
        print(f"\n{len(result.steps)} real tool calls:")
        for i, step in enumerate(result.steps, 1):
            print(f"  {i}. {step.tool_name}(payload={step.payload!r})")
            print(f"     -> {step.result!r}")

        # Real OCEL 2.0 log of this DSPy run's own execution trace (every
        # LM/tool/module call the callback saw, panels included) -- built,
        # schema-validated against the real vendored OCEL 2.0 schema, and
        # persisted, matching this repo's own OCEL-standing discipline: a
        # log is only real evidence once independently validated, not
        # because this call didn't raise.
        if agent.last_ocel_callback is not None:
            ocel_path = (
                Path(__file__).parent.parent
                / "reports"
                / "ocel"
                / "dspy_sregym"
                / f"{episode_id}.ocel.json"
            )
            ocel_log, ocel_digest = write_dspy_ocel_log(ocel_path, agent.last_ocel_callback)
            print(f"\nreal, schema-valid DSPy OCEL log: {ocel_path}")
            print(f"  sha256={ocel_digest}")
            print(f"  {len(ocel_log['events'])} real events across "
                  f"{[t['name'] for t in ocel_log['eventTypes']]}")

        # If the mitigation was submitted, the real conductor evaluates it
        # (and, before that, the diagnosis) synchronously inside its own
        # `submit()` handler and logs the real verdict
        # (`[EVAL] Diagnosis/Mitigation Succeed/Failed`) to its own stdout --
        # never exposed over the public HTTP/MCP surface (confirmed: the
        # only public endpoint, GET /status, returns just the stage marker).
        # `SregymEnvironment.read_log_tail()` (real, on-disk log file, added
        # this session) is the only way to see it. Reached here via a
        # private kernel attribute (`gym._episodes`) -- acceptable in a
        # diagnostic script, not something library code should do.
        if result.diagnosis_submitted or result.mitigation_submitted:
            await asyncio.sleep(3.0)  # let a real, async grading pass settle
            environment = gym._episodes[episode_id].environment
            print(f"\nreal log file: {environment.log_path}")
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
