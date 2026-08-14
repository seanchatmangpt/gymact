#!/usr/bin/env python3
"""Run the real CROWN_P1 (`UnauthorizedActuationPath`) paired episode and write
real OCEL 2.0 logs plus a `CrownPairReceipt` under `reports/ocel/`.

Drives two real `GymAct` episodes against a real `gymact.providers.MemoryProvider`
world -- one per `HumanAccessCondition` -- via `gymact.crown_p1.
run_crown_p1_episode`, then binds them into a `CrownPairReceipt` via
`gymact.crown_p1.bind_counterfactual_pair`. See `gymact/crown_p1.py`'s module
docstring and `.claude/plans/yes-gymact-is-exactly-purrfect-shell.md` for the
composition-admission decision (`ADAPT`) this episode exists to exercise, and
the honest scope note on why standing here is derived from `verify` events
rather than the `act`-event `solved=True` convention most other episode
scripts use.

Usage:
    uv run python scripts/run_crown_p1_episode.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from gymact.authority import AllowListAuthorityResolver
from gymact.crown_p1 import (
    CrownEpisodeRun,
    HumanAccessCondition,
    bind_counterfactual_pair,
    run_crown_p1_episode,
)
from gymact.kernel import GymAct
from gymact.ocel import write_ocel_log
from gymact.providers import MemoryProvider

REPORTS_DIR = Path(__file__).parent.parent / "reports" / "ocel"
AUTHORITY = "urn:gymact:crown-p1:episode-authority"


async def _human_inspector(kernel: GymAct, episode_id: str) -> dict[str, object]:
    """The one, deliberately inert side channel `HumanAccessCondition.ALLOWED`
    permits: a fresh, independent read of episode state, never fed back into
    any kernel call."""
    observation = await kernel.observe(episode_id)
    return dict(observation.state)


async def _run(condition: HumanAccessCondition) -> CrownEpisodeRun:
    provider = MemoryProvider()
    kernel = GymAct(authority_resolver=AllowListAuthorityResolver({AUTHORITY}))
    kernel.register_provider(provider)
    return await run_crown_p1_episode(
        kernel,
        provider,
        condition=condition,
        capability_iri="urn:gymact:memory:capability:set",
        capability_payload={"key": "counter", "value": 1},
        verify_expected={"counter": 1},
        authority_ref=AUTHORITY,
        materialize_config={"requires_authority": True},
        human_inspector=_human_inspector,
    )


async def main() -> None:
    allowed = await _run(HumanAccessCondition.ALLOWED)
    denied = await _run(HumanAccessCondition.DENIED)

    write_ocel_log(REPORTS_DIR / "crown-p1-allowed" / "episode.ocel.json", list(allowed.receipts))
    write_ocel_log(REPORTS_DIR / "crown-p1-denied" / "episode.ocel.json", list(denied.receipts))

    pair = bind_counterfactual_pair(allowed, denied)
    pair_path = REPORTS_DIR / "crown-p1" / "pair-receipt.json"
    pair_path.parent.mkdir(parents=True, exist_ok=True)
    pair_path.write_text(json.dumps(pair.model_dump(mode="json"), indent=2, sort_keys=True))

    print(f"allowed standing:  {pair.allowed_standing}")
    print(f"denied standing:   {pair.denied_standing}")
    print(f"standing invariant holds: {pair.standing_invariant_holds}")
    print(f"unauthorized path found (allowed): {pair.unauthorized_path_found_allowed}")
    print(f"unauthorized path found (denied):  {pair.unauthorized_path_found_denied}")
    print(f"pair receipt written to: {pair_path}")


if __name__ == "__main__":
    asyncio.run(main())
