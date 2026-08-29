#!/usr/bin/env python3
"""Execute the credential-free GCP public contract census and persist evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from gymact.gyms.gcp_public_census import load_public_contract_census


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("reports/gcp/public-contract-census.json"))
    parser.add_argument("--timeout", type=float, default=60.0)
    args = parser.parse_args()

    census = load_public_contract_census(timeout=args.timeout)
    summary = census.summary()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, sort_keys=True))
    return 0 if census.public_sources_alive else 1


if __name__ == "__main__":
    raise SystemExit(main())
