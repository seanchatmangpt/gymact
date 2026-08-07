"""gymact bridge to ggen-legacy's own `ggen-v26-8-1-verifier` binary.

Wraps the verifier's `materialize -> observe -> actuate -> verify -> checkpoint
-> restore -> teardown` lifecycle behind the standard `EnvironmentProvider`/
`Environment` contract (see `gymact.providers.MemoryProvider` for the
precedent this module follows).

The verifier already emits a `CrownReport` whose `standing` field takes the
values `ALIVE` / `PARTIAL_ALIVE` / `BUILD_BROKEN` -- the same vocabulary
`gymact.models.Standing` uses. This bridge does not reinterpret that
vocabulary; it passes the verifier's own report through unchanged.

Scope: this environment's "state" is the verifier's own evidence output
(`.ggen/v26.8.1/verifier-report.json` + `receipt.json`), not the whole
ggen-legacy working tree or git history -- checkpointing arbitrary repo state
is out of scope for a bounded gym world.
"""

from __future__ import annotations

import asyncio
import json
from copy import deepcopy
from pathlib import Path
from typing import Any
from uuid import uuid4

from gymact.models import Capability, Consequence

GGEN_LEGACY_CAPABILITIES = (
    Capability(
        iri="urn:gymact:ggen-legacy:capability:observe",
        title="Run the ggen-legacy v26.8.1 verifier in observe-only (non-strict) mode",
        consequence=Consequence.DO,
        binding="observe",
    ),
    Capability(
        iri="urn:gymact:ggen-legacy:capability:verify",
        title="Run the ggen-legacy v26.8.1 verifier in strict release-admission mode",
        consequence=Consequence.DO,
        binding="verify",
    ),
)

_REPORT_PATH = Path(".ggen/v26.8.1/verifier-report.json")
_RECEIPT_PATH = Path(".ggen/v26.8.1/receipt.json")
_BINARY_RELATIVE = Path("tools/v26.8.1/target/debug/ggen-v26-8-1-verifier")
_MANIFEST_RELATIVE = Path("tools/v26.8.1/Cargo.toml")


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    with path.open("rb") as handle:
        return json.load(handle)


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, sort_keys=True)
        handle.write("\n")


class GgenLegacyVerifierEnvironment:
    """A materialized binding to one ggen-legacy checkout's v26.8.1 verifier."""

    def __init__(self, *, root: Path, requires_authority: bool = True) -> None:
        self.environment_id = f"urn:gymact:ggen-legacy:environment:{uuid4().hex}"
        self.requires_authority = requires_authority
        self._root = root
        self._closed = False
        self._last_report: dict[str, Any] = {}
        self._last_receipt: dict[str, Any] = {}

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("environment is torn down")

    def capabilities(self) -> tuple[Capability, ...]:
        self._ensure_open()
        return GGEN_LEGACY_CAPABILITIES

    async def observe(self) -> dict[str, Any]:
        self._ensure_open()
        return deepcopy(self._last_report)

    async def actuate(self, capability: Capability, payload: dict[str, Any]) -> dict[str, Any]:
        self._ensure_open()
        del payload  # this bridge's two capabilities take no per-call payload
        binding = capability.binding
        if binding == "observe":
            args = ["--root", str(self._root), "--observe-only"]
        elif binding == "verify":
            args = ["--root", str(self._root)]
        else:
            raise ValueError(f"unsupported provider binding: {binding}")

        before = deepcopy(self._last_report)
        exit_code, stderr = await self._run_verifier(args)

        report = _read_json(self._root / _REPORT_PATH) or {}
        receipt = _read_json(self._root / _RECEIPT_PATH) or {}
        self._last_report = report
        self._last_receipt = receipt

        return {
            "before": before,
            "after": deepcopy(report),
            "capability": capability.iri,
            "exit_code": exit_code,
            "stderr": stderr,
        }

    async def _run_verifier(self, args: list[str]) -> tuple[int, str]:
        binary = self._root / _BINARY_RELATIVE
        if binary.is_file():
            command = [str(binary), *args]
        else:
            manifest = self._root / _MANIFEST_RELATIVE
            command = [
                "cargo",
                "run",
                "--manifest-path",
                str(manifest),
                "--bin",
                "ggen-v26-8-1-verifier",
                "--",
                *args,
            ]
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError as error:
            raise RuntimeError(f"could not spawn verifier: {error}") from error
        _, stderr = await process.communicate()
        return process.returncode or 0, stderr.decode("utf-8", errors="replace")

    async def verify(self, expected: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        self._ensure_open()
        observed = await self.observe()
        passed = all(observed.get(key) == value for key, value in expected.items())
        return passed, observed

    async def checkpoint(self) -> dict[str, Any]:
        self._ensure_open()
        return {
            "report": deepcopy(self._last_report),
            "receipt": deepcopy(self._last_receipt),
        }

    async def restore(self, checkpoint: dict[str, Any]) -> None:
        self._ensure_open()
        self._last_report = deepcopy(checkpoint.get("report", {}))
        self._last_receipt = deepcopy(checkpoint.get("receipt", {}))
        if self._last_report:
            _write_json(self._root / _REPORT_PATH, self._last_report)
        if self._last_receipt:
            _write_json(self._root / _RECEIPT_PATH, self._last_receipt)

    async def teardown(self) -> None:
        # Unlike MemoryEnvironment's ephemeral state, .ggen/v26.8.1/ holds real
        # observable evidence -- deleting it on teardown would be destructive
        # for no reason, so teardown only closes this Environment handle.
        self._closed = True


class GgenLegacyVerifierProvider:
    """Materializes `GgenLegacyVerifierEnvironment`s bound to a ggen-legacy checkout."""

    name = "ggen-legacy"
    materialization_requires_authority = True

    async def materialize(
        self, *, scenario: str | None, config: dict[str, Any]
    ) -> GgenLegacyVerifierEnvironment:
        del scenario
        root_value = config.get("root")
        if not isinstance(root_value, str) or not root_value:
            raise TypeError("config.root must be a non-empty string path to a ggen-legacy checkout")
        root = Path(root_value)
        if not root.is_dir():
            raise TypeError(f"config.root does not exist or is not a directory: {root}")
        if not (root / _MANIFEST_RELATIVE).is_file():
            raise TypeError(
                f"config.root does not look like a ggen-legacy checkout "
                f"(missing {_MANIFEST_RELATIVE}): {root}"
            )
        configured = config.get("requires_authority", True)
        if not isinstance(configured, bool):
            raise TypeError("config.requires_authority must be a boolean")
        return GgenLegacyVerifierEnvironment(root=root.resolve(), requires_authority=configured)
