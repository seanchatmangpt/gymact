#!/usr/bin/env python3
"""Execute a declared GCP empirical validation corpus.

Input is a JSON object with ``cases``. Each case supplies case_id, method_id,
effect, http_method, url, and optional query/body/headers. Credentials are read
only from ``GYMACT_GCP_ACCESS_TOKEN`` and are never serialized. Consequential
cases require both ``--allow-do`` and ``--authority-ref``.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from gymact.gyms.gcp_behavior import GcpBehaviorEffect
from gymact.gyms.gcp_live_probe import GcpLiveProbeRequest, execute_live_probe


def _load_cases(path: Path, *, authority_ref: str | None) -> tuple[GcpLiveProbeRequest, ...]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_cases = payload.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise ValueError("campaign.cases must be a non-empty array")
    cases: list[GcpLiveProbeRequest] = []
    identities: set[str] = set()
    for raw in raw_cases:
        if not isinstance(raw, dict):
            raise TypeError("campaign case must be an object")
        request = GcpLiveProbeRequest(
            case_id=str(raw["case_id"]),
            method_id=str(raw["method_id"]),
            effect=GcpBehaviorEffect(str(raw["effect"])),
            http_method=str(raw["http_method"]),
            url=str(raw["url"]),
            query=dict(raw.get("query", {})),
            body=raw.get("body"),
            headers=dict(raw.get("headers", {})),
            authority_ref=authority_ref,
        )
        if request.case_id in identities:
            raise ValueError(f"DUPLICATE_GCP_CAMPAIGN_CASE:{request.case_id}")
        identities.add(request.case_id)
        cases.append(request)
    return tuple(cases)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("campaign", type=Path)
    parser.add_argument("--output", type=Path, default=Path("artifacts/gcp/empirical-campaign.json"))
    parser.add_argument("--allow-do", action="store_true")
    parser.add_argument("--authority-ref")
    parser.add_argument("--timeout", type=float, default=60.0)
    args = parser.parse_args()

    cases = _load_cases(args.campaign, authority_ref=args.authority_ref)
    access_token = os.environ.get("GYMACT_GCP_ACCESS_TOKEN")
    results = [
        execute_live_probe(
            case,
            access_token=access_token,
            allow_do=args.allow_do,
            timeout=args.timeout,
        )
        for case in cases
    ]

    report: dict[str, Any] = {
        "subject": "real-gcp",
        "case_count": len(results),
        "executed_count": sum(result.executed for result in results),
        "standing": "ALIVE" if all(result.executed for result in results) else "PARTIAL_ALIVE",
        "cases": [
            {
                "case_id": result.request.case_id,
                "method_id": result.request.method_id,
                "effect": result.request.effect.value,
                "disposition": result.disposition.value,
                "receipt": result.receipt,
                "reason": result.reason,
                "observation": (
                    {
                        "status_code": result.observation.status_code,
                        "headers": list(result.observation.headers),
                        "body_kind": result.observation.body_kind,
                        "canonical_body": result.observation.canonical_body,
                        "digest_blake3": result.observation.digest_blake3,
                    }
                    if result.observation is not None
                    else None
                ),
            }
            for result in results
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("subject", "case_count", "executed_count", "standing")}, sort_keys=True))
    return 0 if all(result.executed for result in results) else 2


if __name__ == "__main__":
    raise SystemExit(main())
