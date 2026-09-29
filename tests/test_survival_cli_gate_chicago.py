"""CLI-to-observation-closure gate tests over real files.

The survival CLI (``gymact-survival``, argparse) exposes no observation-closure
command; closure lives in ``qualify_campaign_observation_closure``. These tests
run the real CLI in a real subprocess, read the ``campaign.jsonl`` it wrote, and
present that corpus to the closure gate: complete accepted, incomplete refused
with typed missing-case evidence. They also pin the CLI's typed refusal text on
stderr for a too-small campaign bound (exit codes alone are covered in
``test_survival_cli.py``).
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from gymact.survival_campaign_observation import qualify_campaign_observation_closure
from gymact.survival_cli import manufacture_canonical_artifacts

SUBJECT = "git:seanchatmangpt/gymact@0123456789abcdef"
WORKLOAD = "sha256:gate-workload"
HORIZON = 3


def _run_cli(output: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "gymact.survival_cli",
            "--subject",
            SUBJECT,
            "--workload-id",
            WORKLOAD,
            "--scenario-id",
            "gate",
            "--horizon",
            str(HORIZON),
            "--output-dir",
            str(output),
            *extra,
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def _expected_campaign():
    _, _, campaign = manufacture_canonical_artifacts(
        subject=SUBJECT,
        workload_id=WORKLOAD,
        scenario_id="gate",
        horizon=HORIZON,
        repetitions=1,
        seed_base=0,
        max_cases=100_000,
        max_campaign_cases=250_000,
    )
    return campaign


@pytest.fixture(scope="module")
def materialized(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, object]:
    """One real CLI materialization + its independently recomputed campaign, shared
    read-only by the closure tests (tests write any modified corpus into their own
    tmp_path, never into this directory)."""
    output = tmp_path_factory.mktemp("gate") / "out"
    result = _run_cli(output)
    assert result.returncode == 0, result.stderr
    return output, _expected_campaign()


def _read_corpus(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_cli_materialized_corpus_is_accepted_by_closure_gate(
    materialized: tuple[Path, object],
) -> None:
    output, campaign = materialized
    summary = json.loads((output / "receipts.json").read_text(encoding="utf-8"))
    campaign_bytes = (output / "campaign.jsonl").read_bytes()
    assert summary["campaign_artifact"]["sha256"] == hashlib.sha256(campaign_bytes).hexdigest()

    assert summary["campaign_digest"] == campaign.campaign_digest
    documents = _read_corpus(output / "campaign.jsonl")
    closure = qualify_campaign_observation_closure(campaign, documents)

    assert len(documents) == summary["campaign_case_count"] == len(campaign.cases)
    assert closure.complete is True
    assert closure.standing == "STRUCTURAL"
    assert closure.observed_unique_case_count == closure.expected_case_count == len(documents)
    assert closure.missing_case_ids == ()
    assert closure.actuation_performed is False
    assert closure.authority == "none"


def test_cli_materialized_corpus_missing_a_variant_is_refused_with_typed_ids(
    materialized: tuple[Path, object], tmp_path: Path
) -> None:
    output, campaign = materialized
    lines = (output / "campaign.jsonl").read_text(encoding="utf-8").splitlines()
    dropped = json.loads(lines[7])["episode_id"]
    truncated = tmp_path / "incomplete.jsonl"
    truncated.write_text("\n".join(lines[:7] + lines[8:]) + "\n", encoding="utf-8")

    closure = qualify_campaign_observation_closure(campaign, _read_corpus(truncated))

    assert closure.complete is False
    assert closure.standing == "PARTIAL"
    assert closure.missing_case_ids == (dropped,)
    assert closure.observed_unique_case_count == len(campaign.cases) - 1
    assert closure.unknown_case_ids == ()
    assert closure.duplicate_case_ids == ()
    assert closure.identity_drift_episode_ids == ()


def test_cli_materialized_corpus_with_duplicate_and_drifted_variants_is_refused(
    materialized: tuple[Path, object],
) -> None:
    output, campaign = materialized
    documents = _read_corpus(output / "campaign.jsonl")
    duplicated = documents[0]["episode_id"]
    drifted = documents[1]["episode_id"]
    documents[1]["gymact"]["campaign_spec_digest"] = "0" * 64
    documents.append(documents[0])

    closure = qualify_campaign_observation_closure(campaign, documents)

    assert closure.complete is False
    assert closure.standing == "PARTIAL"
    assert closure.duplicate_case_ids == (duplicated,)
    assert closure.identity_drift_episode_ids == (drifted,)
    assert closure.missing_case_ids == ()


def test_cli_bound_refusal_names_reason_on_stderr_and_writes_nothing(tmp_path: Path) -> None:
    output = tmp_path / "too-small"
    result = _run_cli(output, "--max-campaign-cases", "10")

    assert result.returncode == 2
    assert result.stdout == ""
    assert result.stderr.startswith("survival-campaign-refused: ")
    assert len(result.stderr.strip()) > len("survival-campaign-refused:")
    assert not output.exists()


def test_cli_overwrite_refusal_names_reason_and_preserves_existing_bytes(
    materialized: tuple[Path, object], tmp_path: Path
) -> None:
    output = tmp_path / "out"
    shutil.copytree(
        materialized[0], output
    )  # private copy: a bad refusal must not corrupt the shared one
    before = {p.name: p.read_bytes() for p in output.iterdir()}

    result = _run_cli(output)

    assert result.returncode == 2
    assert (
        result.stderr.strip() == "survival-campaign-refused: output exists; use --force to replace"
    )
    assert {p.name: p.read_bytes() for p in output.iterdir()} == before
