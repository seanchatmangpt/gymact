from __future__ import annotations

import json
from pathlib import Path

from gymact.survival_cli import main, manufacture_canonical_artifacts


def test_canonical_manufacture_closes_full_suite_without_actuation() -> None:
    experiment, manifest, campaign = manufacture_canonical_artifacts(
        subject="git:seanchatmangpt/gymact@0123456789abcdef",
        workload_id="sha256:canonical-cli-workload",
        scenario_id="canonical",
        horizon=10,
        repetitions=1,
        seed_base=0,
        max_cases=100_000,
        max_campaign_cases=250_000,
    )

    assert experiment.case_count == 405
    assert len(manifest.cases) == 405
    assert len(campaign.cases) == 5_265
    assert len({case.campaign_case_id for case in campaign.cases}) == 5_265
    assert all(case.authority == "none" for case in campaign.cases)
    assert all(case.actuation_performed is False for case in campaign.cases)


def test_cli_writes_manifest_campaign_and_exact_receipts(tmp_path: Path) -> None:
    output = tmp_path / "survival"

    exit_code = main(
        [
            "--subject",
            "git:seanchatmangpt/gymact@0123456789abcdef",
            "--workload-id",
            "sha256:cli-workload",
            "--scenario-id",
            "cli",
            "--horizon",
            "5",
            "--output-dir",
            str(output),
        ]
    )

    assert exit_code == 0
    assert (output / "manifest.json").exists()
    assert (output / "campaign.jsonl").exists()
    summary = json.loads((output / "receipts.json").read_text(encoding="utf-8"))
    assert summary["experiment_case_count"] == 405
    assert summary["campaign_case_count"] == 5_265
    assert summary["manifest_artifact"]["record_count"] == 405
    assert summary["campaign_artifact"]["record_count"] == 5_265
    assert summary["authority"] == "none"
    assert summary["actuation_performed"] is False


def test_cli_refuses_silent_overwrite_and_allows_explicit_force(tmp_path: Path) -> None:
    output = tmp_path / "survival"
    args = [
        "--subject",
        "subject",
        "--workload-id",
        "workload",
        "--horizon",
        "3",
        "--output-dir",
        str(output),
    ]

    assert main(args) == 0
    first_receipt = (output / "receipts.json").read_bytes()
    assert main(args) == 2
    assert (output / "receipts.json").read_bytes() == first_receipt
    assert main(args + ["--force"]) == 0


def test_cli_refuses_campaign_when_bound_is_below_manufactured_width(tmp_path: Path) -> None:
    exit_code = main(
        [
            "--subject",
            "subject",
            "--workload-id",
            "workload",
            "--horizon",
            "3",
            "--max-campaign-cases",
            "5000",
            "--output-dir",
            str(tmp_path / "too-small"),
        ]
    )

    assert exit_code == 2
    assert not (tmp_path / "too-small" / "campaign.jsonl").exists()
