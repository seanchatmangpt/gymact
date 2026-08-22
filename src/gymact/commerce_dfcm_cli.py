"""Command-line crown for the marketplace-free Post-AGI DfCM commerce world."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import anyio

from gymact.commerce_dfcm import CommerceSelectedPlan, execute_commerce_dfcm
from gymact.models import Standing


def _load_plan(path: Path) -> CommerceSelectedPlan:
    value: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("COMMERCE_DFCM_PLAN_MUST_BE_OBJECT")
    return CommerceSelectedPlan.model_validate(value)


async def run_plan(plan: CommerceSelectedPlan) -> dict[str, Any]:
    """Execute one selected design and return its canonical JSON-compatible receipt."""
    result = await execute_commerce_dfcm(plan)
    payload = result.model_dump(mode="json")
    payload["crown"] = (
        result.standing is Standing.ALIVE
        and result.internal_standing is Standing.ALIVE
        and result.external_standing is Standing.BLOCKED
        and result.verified
        and not result.marketplace_attempted
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="gymact-commerce-dfcm",
        description=(
            "Execute the bounded Post-AGI DfCM commerce crown without marketplace DO."
        ),
    )
    parser.add_argument(
        "--plan",
        required=True,
        type=Path,
        help="JSON file containing the eight CommerceSelectedPlan factors.",
    )
    args = parser.parse_args()
    payload = anyio.run(run_plan, _load_plan(args.plan))
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    if not payload["crown"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
