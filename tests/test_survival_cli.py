from __future__ import annotations

import json

from gymact.survival_cli import main


def spec() -> dict:
    return {
        "experiment_id": "cli:v26.9.25",
        "scenarios": [
            {
                "scenario_id": "world",
                "subject": "git:gymact/example@0123456789abcdef",
                "workload_id": "sha256:cli",
                "horizon": 2,
                "terminal_predicate_ref": "urn:goal",
            }
        ],
        "policies": [
            {
                "policy_id": "formal",
                "machinery": "formal-generated",
                "information_topology": "receipt-only",
                "tool_policy": "optional",
            }
        ],
        "factors": [
            {
                "name": "transport",
                "levels": ["stable", "lossy"],
            }
        ],
        "repetitions": 1,
        "seed_base": 7,
    }


def test_cli_materializes_manifest_then_accepts_complete_observation_corpus(
    tmp_path,
) -> None:
    experiment = tmp_path / "experiment.json"
    manifest = tmp_path / "manifest.json"
    observations = tmp_path / "observations.json"
    closure = tmp_path / "closure.json"
    experiment.write_text(json.dumps(spec()), encoding="utf-8")

    assert main(["manifest", str(experiment), str(manifest)]) == 0
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert len(payload["cases"]) == 2
    assert payload["authority"] == "none"

    docs = []
    for case in payload["cases"]:
        docs.append(
            {
                "schema": "autofde-lab.premature-actuation-episode/1",
                "subject": "git:gymact/example@0123456789abcdef",
                "workload_id": "sha256:cli",
                "policy_id": case["analysis_policy_id"],
                "episode_id": case["case_id"],
                "horizon": 2,
                "events": [],
                "gymact": {
                    "run_case_id": case["case_id"],
                    "scenario_id": case["scenario_id"],
                    "repetition": case["repetition"],
                    "seed": case["seed"],
                },
            }
        )
    observations.write_text(json.dumps(docs), encoding="utf-8")

    assert (
        main(
            [
                "closure",
                str(manifest),
                str(observations),
                str(closure),
                "--gate",
            ]
        )
        == 0
    )
    receipt = json.loads(closure.read_text(encoding="utf-8"))
    assert receipt["complete"] is True
    assert receipt["standing"] == "STRUCTURAL"
    assert receipt["authority"] == "none"


def test_cli_gate_fails_on_incomplete_corpus(tmp_path) -> None:
    experiment = tmp_path / "experiment.json"
    manifest = tmp_path / "manifest.json"
    observations = tmp_path / "observations.json"
    closure = tmp_path / "closure.json"
    experiment.write_text(json.dumps(spec()), encoding="utf-8")
    assert main(["manifest", str(experiment), str(manifest)]) == 0
    observations.write_text("[]", encoding="utf-8")

    assert (
        main(
            [
                "closure",
                str(manifest),
                str(observations),
                str(closure),
                "--gate",
            ]
        )
        == 1
    )
    receipt = json.loads(closure.read_text(encoding="utf-8"))
    assert receipt["complete"] is False
    assert receipt["missing_case_ids"]
