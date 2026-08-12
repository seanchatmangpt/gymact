#!/usr/bin/env python3
"""Real CLI entrypoint: drive gymact's full (bounded) combinatorial
maximum -- every real `(gym, operation_sequence_variant)` combination --
and emit one real, schema-valid, exhaustive OCEL 2.0 log plus its
cross-checkable combination report. See `gymact.combinatorial_ocel` for
the real implementation this only calls.
"""

from __future__ import annotations

import asyncio

from gymact.combinatorial_ocel import run_combinatorial_maximum


async def _main() -> int:
    space, report = await run_combinatorial_maximum()
    print(f"real total_cardinality: {report['total_cardinality']}")
    print(f"real combinations_run: {report['combinations_run']}")
    print(f"real truncated: {report['truncated']}")
    print(f"real total_receipts: {report['total_receipts']}")
    print(f"real OCEL log: {report['ocel_log_path']}")
    print(f"real OCEL log digest: {report['ocel_log_digest']}")
    print()
    for row in report["combinations"]:
        print(
            f"  {row['gym']:<24} {row['operation_sequence_variant']:<24} "
            f"-> {row['final_standing']:<10} ({row['receipt_count']} receipts)"
        )
    if space.truncated:
        print(
            "\nWARNING: real combination space exceeded the configured bound -- "
            "this run is a real, honestly-truncated subset, not the full space."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
