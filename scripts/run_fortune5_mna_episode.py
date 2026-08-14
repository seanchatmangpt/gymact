#!/usr/bin/env python3
"""Execute the bounded synthetic Fortune-5 M&A episode and emit its receipt summary."""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from gymact.mna import MnaSelectedPlan, execute_fortune5_mna_simulation


DEFAULT_PLAN = MnaSelectedPlan(
    transaction_form="stock_purchase",
    consideration="mixed",
    integration_topology="federate",
    operating_model="business_unit",
    separation_strategy="transitional_services",
    regulatory_sequence="clear_then_sign",
)


async def _run(output: Path | None) -> int:
    result = await execute_fortune5_mna_simulation(DEFAULT_PLAN)
    document = result.model_dump(mode="json")
    text = json.dumps(document, indent=2, sort_keys=True) + "\n"
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if result.verified else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    return asyncio.run(_run(args.output))


if __name__ == "__main__":
    raise SystemExit(main())
