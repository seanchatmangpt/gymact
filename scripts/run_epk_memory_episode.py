#!/usr/bin/env python3
"""Real, live proof that `gymact.epistemic_process_kernel.run_episode` is a
genuine, provider-agnostic toolkit -- not a piece of sregym-specific
machinery that happens to have generic-looking types. Runs the SAME kernel
code (`run_episode`/`explain_episode`) used by `run_epk_sregym_diagnosis.py`
against a completely different, in-process `gymact.providers.MemoryProvider`
world instead of a real Kubernetes cluster.

Deliberately a fast, in-process demo (no live cluster, no MCP servers,
completes in seconds) rather than a second slow live-cluster run -- the
point is proving the KERNEL generalizes, which this does just as validly
without spending real cluster minutes on it.

Also deliberately exercises the real, corrected capability-classification
fix: `MemoryProvider`'s only capabilities (`set`/`delete`/`increment`) are
genuinely mutating DO operations with no safe, read-only investigatory
capability at all -- unlike sregym's `run_kubectl`. `read_capability_bindings`
is honestly empty here, proving `run_episode` handles "nothing available to
discriminate with" gracefully rather than assuming every provider has one.

Usage:
    set -a; source ~/.env; set +a
    uv run python scripts/run_epk_memory_episode.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from gymact import AllowListAuthorityResolver, GymAct, MaterializationIntent
from gymact.epistemic_dspy import Constraint, Fact, Goal
from gymact.epistemic_process_kernel import explain_episode, run_episode
from gymact.providers import MemoryProvider

AUTHORITY = "urn:gymact:script:epk-memory-episode"


async def main() -> None:
    if not os.environ.get("GROQ_API_KEY"):
        print("REFUSED: GROQ_API_KEY not set in this environment", file=sys.stderr)
        sys.exit(1)

    gym = GymAct(authority_resolver=AllowListAuthorityResolver({AUTHORITY}))
    gym.register_provider(MemoryProvider())

    # Real, deliberately broken initial state -- `retry_limit` should be a
    # positive integer usable by real retry logic; it's 0.
    materialization = await gym.materialize(
        MaterializationIntent(
            provider="memory",
            config={"initial": {"retry_limit": 0, "max_backoff_ms": 500}},
            authority_ref=AUTHORITY,
        )
    )
    if not materialization.accepted:
        print(f"REFUSED at materialize: {materialization.receipt.reason}", file=sys.stderr)
        sys.exit(1)
    episode_id = materialization.episode.episode_id
    print(f"episode_id={episode_id}")

    try:
        # Real seed fact from a real `gym.observe()` call -- the same
        # discipline as sregym's own `_gather_seed_facts`, just against a
        # trivially simple real world instead of a real cluster.
        observation = await gym.observe(episode_id)
        seed_facts = [
            Fact(
                id=f"fact:{key}",
                subject=f"memory:{key}",
                predicate="value",
                value=str(value),
                source_observation_ids=[],
                derivation_ids=["gym.observe"],
            )
            for key, value in observation.state.items()
        ]
        print(f"real seed facts: {[f.model_dump() for f in seed_facts]}")

        goal = Goal(
            id="goal:fix-retry-limit",
            desired_predicates=["memory:retry_limit is a positive integer usable for retries"],
            prohibited_predicates=[],
            success_criteria=["retry_limit is set to a real, positive integer value"],
        )
        constraints = [
            Constraint(
                id="constraint:grounding",
                expression="every hypothesis state and evidence link must be grounded "
                "in real, cited facts -- never asserted without a real fact_id",
                hard=True,
            )
        ]

        # Real, honest classification for THIS provider: no capability here
        # is a safe, read-only investigatory operation, so
        # `read_capability_bindings` is genuinely empty -- proving
        # `run_episode` doesn't assume every provider has one.
        result = await run_episode(
            gym,
            episode_id,
            AUTHORITY,
            goal,
            constraints,
            seed_facts,
            read_capability_bindings=set(),
            do_capability_bindings={"set", "delete", "increment"},
            judge_model_id="groq/openai/gpt-oss-120b",
            max_discriminate_rounds=3,
        )

        lesson, lesson_why = await explain_episode(
            result, goal, judge_model_id="groq/openai/gpt-oss-120b"
        )
        print("\n=== senior-engineer walkthrough of this real episode ===")
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
        if result.selected_plan is not None:
            print(f"selected_plan={result.selected_plan.name!r}")
            for step in result.selected_plan.steps:
                print(f"  step: {step.capability_id} params={step.parameters!r}")
        print(f"\n{len(result.steps)} real kernel steps:")
        for i, step in enumerate(result.steps, 1):
            print(f"  {i}. {step.kind}(payload={step.payload!r})")

        # Real, final, independent read of the actual mutated world state --
        # confirms whether a real DO capability actually changed anything,
        # not just whether the kernel claims it did.
        final_observation = await gym.observe(episode_id)
        print(f"\nreal final world state: {final_observation.state!r}")
    finally:
        teardown_receipt = await gym.teardown(episode_id, authority_ref=AUTHORITY)
        print(f"\nteardown standing={teardown_receipt.standing.value}")


if __name__ == "__main__":
    asyncio.run(main())
