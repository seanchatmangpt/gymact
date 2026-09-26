"""CLI for manufacturing survival manifests and qualifying observation closure."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from gymact.survival_experiment import SurvivalExperiment
from gymact.survival_manifest import SurvivalExperimentManifest, build_survival_manifest
from gymact.survival_observation import qualify_observation_closure


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _experiment(path: Path) -> SurvivalExperiment:
    value = _read_json(path)
    if not isinstance(value, dict):
        raise ValueError("SURVIVAL_EXPERIMENT_SPEC_NOT_OBJECT")
    return SurvivalExperiment.model_validate(value)


def _manifest(path: Path) -> SurvivalExperimentManifest:
    value = _read_json(path)
    if not isinstance(value, dict):
        raise ValueError("SURVIVAL_MANIFEST_NOT_OBJECT")
    value = dict(value)
    value.pop("manifest_digest", None)
    return SurvivalExperimentManifest.model_validate(value)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    subparsers = parser.add_subparsers(dest="command", required=True)

    manifest_parser = subparsers.add_parser("manifest")
    manifest_parser.add_argument("experiment", type=Path)
    manifest_parser.add_argument("out", type=Path)

    closure_parser = subparsers.add_parser("closure")
    closure_parser.add_argument("manifest", type=Path)
    closure_parser.add_argument("observations", type=Path)
    closure_parser.add_argument("out", type=Path)
    closure_parser.add_argument("--gate", action="store_true")

    args = parser.parse_args(argv)

    if args.command == "manifest":
        manifest = build_survival_manifest(_experiment(args.experiment))
        _write_json(args.out, manifest.to_json())
        print(
            json.dumps(
                {
                    "manifest_digest": manifest.manifest_digest,
                    "case_count": len(manifest.cases),
                    "authority": manifest.authority,
                },
                sort_keys=True,
            )
        )
        return 0

    manifest = _manifest(args.manifest)
    observations = _read_json(args.observations)
    if not isinstance(observations, list) or not all(
        isinstance(item, dict) for item in observations
    ):
        raise ValueError("SURVIVAL_OBSERVATIONS_NOT_LIST_OF_OBJECTS")
    closure = qualify_observation_closure(manifest, observations)
    _write_json(args.out, closure.model_dump(mode="json"))
    print(
        json.dumps(
            {
                "complete": closure.complete,
                "standing": closure.standing,
                "observed_unique_case_count": closure.observed_unique_case_count,
                "expected_case_count": closure.expected_case_count,
            },
            sort_keys=True,
        )
    )
    return 1 if args.gate and not closure.complete else 0


if __name__ == "__main__":
    raise SystemExit(main())
