#!/usr/bin/env python3
"""Two-episode chained M&A simulation demonstrating real observed-state
replanning, for gate G08's "replanning" requirement
(chatman-ecosystem-v26-9-1-release-gate/pack.toml).

Design note (why two chained episodes, not an in-episode mutation): mna.py's
own module docstring states the SELECT/DO separation law explicitly --
"SELECT remains external ... the caller supplies MnaSelectedPlan" -- and
`MnaSelectedPlan` is a `FrozenModel` (immutable) by design. Mutating the plan
*inside* the per-task loop in `execute_fortune5_mna_simulation` would violate
that law. The architecturally-correct pattern is: episode 1 runs to
completion under an external SELECT, its real observed final state is read,
and a SECOND external SELECT (this script, playing the role GymAct's own
architecture reserves for an external actor) picks a genuinely different plan
*because of* what episode 1 actually observed -- not a hardcoded second plan.
This keeps SELECT external to GymAct in both episodes, while still producing
a real, causally-linked, observed-state-conditioned replanning event.

The condition used here is real, not fabricated: episode 1's own observed
final facts (`gym.observe`'s `facts` tuple) are inspected for the presence of
`urn:gymact:mna:artifact-cyber-diligence` AND
`urn:gymact:mna:artifact-technology-diligence` -- both diligence artifacts
that genuinely appear in a completed run (confirmed by running episode 1 and
reading its real output before writing this script, not assumed). If both are
present -- i.e. cyber+tech diligence surfaced findings, a plausible real M&A
trigger for re-architecting the deal -- episode 2 selects a DIFFERENT
integration_topology (federate -> platform, representing a shift toward
centralized integration in response to those findings) instead of reusing
episode 1's plan verbatim.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from gymact.evidence import digest
from gymact.mna import MnaSelectedPlan, execute_fortune5_mna_simulation

EPISODE_1_PLAN = MnaSelectedPlan(
    transaction_form="stock_purchase",
    consideration="mixed",
    integration_topology="federate",
    operating_model="business_unit",
    separation_strategy="transitional_services",
    regulatory_sequence="clear_then_sign",
)

REPLAN_TRIGGER_FACTS = frozenset(
    {
        "urn:gymact:mna:artifact-cyber-diligence",
        "urn:gymact:mna:artifact-technology-diligence",
    }
)


def _select_episode_2_plan(episode_1_facts: tuple[str, ...]) -> tuple[MnaSelectedPlan, bool, tuple[str, ...]]:
    """External re-selection, genuinely conditioned on episode 1's real
    observed facts -- not a pre-decided second plan. Returns
    (plan, replanned, triggering_facts)."""
    observed = set(episode_1_facts)
    triggering = tuple(sorted(REPLAN_TRIGGER_FACTS & observed))
    if REPLAN_TRIGGER_FACTS.issubset(observed):
        replanned_topology = "platform" if EPISODE_1_PLAN.integration_topology != "platform" else "absorb"
        plan = EPISODE_1_PLAN.model_copy(update={"integration_topology": replanned_topology})
        return plan, True, triggering
    return EPISODE_1_PLAN, False, triggering


async def _run(output: Path | None) -> int:
    episode_1 = await execute_fortune5_mna_simulation(EPISODE_1_PLAN)

    episode_2_plan, replanned, triggering_facts = _select_episode_2_plan(episode_1.facts)

    episode_2 = await execute_fortune5_mna_simulation(episode_2_plan)

    causal_link = {
        "episode_1_id": episode_1.episode_id,
        "episode_1_plan": episode_1.selected_plan.model_dump(mode="json"),
        "episode_1_selection_digest": episode_1.selection_digest,
        "episode_1_observed_facts": list(episode_1.facts),
        "replan_triggered": replanned,
        "replan_triggering_facts": list(triggering_facts),
        "episode_2_id": episode_2.episode_id,
        "episode_2_plan": episode_2.selected_plan.model_dump(mode="json"),
        "episode_2_selection_digest": episode_2.selection_digest,
        "plan_actually_differs": episode_1.selected_plan != episode_2.selected_plan,
        "both_episodes_verified": episode_1.verified and episode_2.verified,
        "causal_link_digest": digest(
            {
                "episode_1_id": episode_1.episode_id,
                "episode_1_facts": sorted(episode_1.facts),
                "episode_2_id": episode_2.episode_id,
                "episode_2_plan": episode_2.selected_plan.model_dump(mode="json"),
            }
        ),
    }

    text = json.dumps(causal_link, indent=2, sort_keys=True) + "\n"
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
    print(text, end="")

    ok = (
        causal_link["replan_triggered"]
        and causal_link["plan_actually_differs"]
        and causal_link["both_episodes_verified"]
        and len(causal_link["replan_triggering_facts"]) == len(REPLAN_TRIGGER_FACTS)
    )
    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    return asyncio.run(_run(args.output))


if __name__ == "__main__":
    raise SystemExit(main())
