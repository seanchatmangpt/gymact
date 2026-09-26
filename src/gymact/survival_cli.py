"""CLI for manufacturing canonical GymAct survival qualification artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from gymact.survival_artifacts import (
    write_survival_campaign_jsonl,
    write_survival_manifest,
)
from gymact.survival_campaign import SurvivalCampaignSpec, manufacture_survival_campaign
from gymact.survival_experiment import SurvivalExperiment, SurvivalScenario
from gymact.survival_manifest import build_survival_manifest
from gymact.survival_suite import (
    canonical_fault_kinds,
    canonical_fault_suite,
    canonical_policy_suite,
    canonical_trace_template,
)


def manufacture_canonical_artifacts(
    *,
    subject: str,
    workload_id: str,
    scenario_id: str,
    horizon: int,
    repetitions: int,
    seed_base: int,
    max_cases: int,
    max_campaign_cases: int,
):
    scenario = SurvivalScenario(
        scenario_id=scenario_id,
        subject=subject,
        workload_id=workload_id,
        horizon=horizon,
        terminal_predicate_ref="urn:gymact:survival:terminal-ready",
    )
    experiment = SurvivalExperiment(
        experiment_id=f"survival:{scenario_id}:h{horizon}",
        scenarios=(scenario,),
        policies=canonical_policy_suite(),
        factors=canonical_fault_suite(),
        repetitions=repetitions,
        seed_base=seed_base,
        max_cases=max_cases,
    )
    manifest = build_survival_manifest(experiment)
    campaign = manufacture_survival_campaign(
        SurvivalCampaignSpec(
            campaign_id=f"campaign:{experiment.experiment_id}",
            experiment=experiment,
            template=canonical_trace_template(horizon),
            fault_kinds=canonical_fault_kinds(),
            max_campaign_cases=max_campaign_cases,
        )
    )
    return experiment, manifest, campaign


def _write_summary(path: Path, value: dict) -> None:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ) + "\n"
    path.write_text(payload, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subject", required=True)
    parser.add_argument("--workload-id", required=True)
    parser.add_argument("--scenario-id", default="canonical")
    parser.add_argument("--horizon", type=int, default=10)
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("--seed-base", type=int, default=0)
    parser.add_argument("--max-cases", type=int, default=100_000)
    parser.add_argument("--max-campaign-cases", type=int, default=250_000)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--force",
        action="store_true",
        help="replace existing generated artifact files",
    )
    args = parser.parse_args(argv)

    manifest_path = args.output_dir / "manifest.json"
    campaign_path = args.output_dir / "campaign.jsonl"
    receipt_path = args.output_dir / "receipts.json"
    targets = (manifest_path, campaign_path, receipt_path)
    if not args.force and any(path.exists() for path in targets):
        print(
            "survival-campaign-refused: output exists; use --force to replace",
            file=sys.stderr,
        )
        return 2

    try:
        experiment, manifest, campaign = manufacture_canonical_artifacts(
            subject=args.subject,
            workload_id=args.workload_id,
            scenario_id=args.scenario_id,
            horizon=args.horizon,
            repetitions=args.repetitions,
            seed_base=args.seed_base,
            max_cases=args.max_cases,
            max_campaign_cases=args.max_campaign_cases,
        )
        args.output_dir.mkdir(parents=True, exist_ok=True)
        manifest_receipt = write_survival_manifest(manifest_path, manifest)
        campaign_receipt = write_survival_campaign_jsonl(campaign_path, campaign)
        summary = {
            "schema": "gymact.survival-campaign-receipts/1",
            "experiment_id": experiment.experiment_id,
            "experiment_case_count": experiment.case_count,
            "manifest_digest": manifest.manifest_digest,
            "campaign_id": campaign.campaign_id,
            "campaign_digest": campaign.campaign_digest,
            "campaign_case_count": len(campaign.cases),
            "manifest_artifact": manifest_receipt.model_dump(mode="json"),
            "campaign_artifact": campaign_receipt.model_dump(mode="json"),
            "authority": "none",
            "actuation_performed": False,
        }
        _write_summary(receipt_path, summary)
    except Exception as exc:
        print(f"survival-campaign-refused: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
