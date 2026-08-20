#!/usr/bin/env python3
"""CONSTRUCT-only DfCM completion driver.

Input JSON shape:
{
  "subject_ref": "repo@sha",
  "max_plans": 4096,
  "items": [CompletionItem-shaped objects]
}

The command prints the maximal bounded reversible frontier plus the deterministic
admitted cut. It never executes a move and therefore never bypasses BRCE.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from gymact.dfcm_finish import CompletionItem, manufacture_and_admit_completion


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("DFCM_FINISH_INPUT_MUST_BE_OBJECT")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description="Manufacture a CONSTRUCT-only DfCM finish cut")
    parser.add_argument("request", type=Path)
    args = parser.parse_args()

    request = _load(args.request)
    subject_ref = str(request.get("subject_ref", "")).strip()
    items = tuple(CompletionItem.model_validate(item) for item in request.get("items", ()))
    max_plans = int(request.get("max_plans", 4096))

    frontier, cut = manufacture_and_admit_completion(
        subject_ref=subject_ref,
        items=items,
        max_plans=max_plans,
    )
    print(
        json.dumps(
            {
                "mode": "CONSTRUCT",
                "frontier": frontier.model_dump(mode="json"),
                "cut": cut.model_dump(mode="json"),
                "direct_actuation": False,
            },
            sort_keys=True,
        )
    )
    return 0 if cut.standing in {"ALIVE", "PARTIAL_ALIVE"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
