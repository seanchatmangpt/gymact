"""Run the model-free, human-free FDE factory simulation and print the cost curves.

    PYTHONPATH=src python scripts/run_fde_factory_sim.py [--out reports/fde_factory_sim.json]

Output is a SIMULATION report (origin=SIMULATED, observed_execution=false); it is not OCEL
standing for any real gym or customer workflow.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from gymact.fde_factory_sim import run_simulation


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    report = run_simulation()
    f, b = report.factory, report.baseline
    print(
        f"origin={report.origin} observed_execution={report.observed_execution} "
        f"llm_calls={report.llm_calls} human_interactions={report.human_interactions}"
    )
    print(f"report_digest={report.report_digest}")
    print(f"{'arm':9} {'cognition_evals':>15} {'verify_evals':>12} {'lookups':>8}")
    for arm in (b, f):
        print(f"{arm.arm:9} {arm.cognition_evals:15d} {arm.verify_evals:12d} {arm.lookups:8d}")
    print(
        f"redundant_explorations(factory)={f.redundant_explorations} "
        f"unverified_consequences(factory)={f.unverified_consequences}"
    )
    for curve in f.curves:
        print(curve.class_id, list(curve.cognition_evals_per_engagement))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(report.model_dump_json(indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
