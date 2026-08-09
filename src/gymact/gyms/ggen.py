"""Bounded real-ggen gym.

The subject is the current `ggen` CLI. Materialization copies an admitted,
dependency-closed ggen consumer project into a private temporary workspace;
`sync run` can therefore never mutate the caller's source tree.
"""
from __future__ import annotations

import asyncio
import hashlib
import shutil
import tempfile
import tomllib
from pathlib import Path
from typing import Any
from uuid import uuid4

from gymact.models import Capability, Consequence

GGEN_CAPABILITIES = (
    Capability(iri="urn:gymact:ggen:capability:graph-validate", title="Validate the admitted ggen graph/templates", consequence=Consequence.READ, binding="graph-validate"),
    Capability(iri="urn:gymact:ggen:capability:doctor", title="Inspect ggen project health", consequence=Consequence.READ, binding="doctor"),
    Capability(iri="urn:gymact:ggen:capability:sync", title="Manufacture project projections with ggen sync run", consequence=Consequence.DO, binding="sync"),
    Capability(iri="urn:gymact:ggen:capability:receipt-verify", title="Verify ggen's latest manufacturing receipt", consequence=Consequence.READ, binding="receipt-verify"),
)

_IGNORED_PARTS = {".git", "__pycache__", ".pytest_cache", "target"}
_MAX_FILES_DEFAULT = 512
_MAX_BYTES_DEFAULT = 8 * 1024 * 1024


def _snapshot(root: Path, *, max_files: int, max_bytes: int) -> dict[str, Any]:
    records: list[tuple[str, str, int]] = []
    total_bytes = 0
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        relative = path.relative_to(root)
        if any(part in _IGNORED_PARTS for part in relative.parts):
            continue
        data = path.read_bytes()
        total_bytes += len(data)
        if len(records) >= max_files:
            raise RuntimeError("BLOCKED:GGEN_GYM_FILE_LIMIT")
        if total_bytes > max_bytes:
            raise RuntimeError("BLOCKED:GGEN_GYM_BYTE_LIMIT")
        records.append((relative.as_posix(), hashlib.sha256(data).hexdigest(), len(data)))
    digest = hashlib.sha256()
    for path, content_digest, size in records:
        digest.update(f"{path}\0{content_digest}\0{size}\n".encode())
    return {
        "tree_digest": digest.hexdigest(),
        "file_count": len(records),
        "total_bytes": total_bytes,
        "files": [{"path": path, "sha256": content_digest, "bytes": size} for path, content_digest, size in records],
        "receipt_present": (root / ".ggen" / "receipts" / "latest.json").is_file(),
    }


def _require_dependency_closed_consumer(source: Path) -> None:
    manifest = tomllib.loads((source / "ggen.toml").read_text(encoding="utf-8"))
    for name, config in (manifest.get("packs") or {}).items():
        if not isinstance(config, dict):
            continue
        pack_path = config.get("path")
        if not isinstance(pack_path, str):
            continue
        candidate = Path(pack_path)
        if candidate.is_absolute() or ".." in candidate.parts:
            raise ValueError(f"REFUSED:GGEN_EXTERNAL_PACK_PATH:{name}")
        mounted = source / candidate
        if not mounted.exists():
            raise ValueError(f"BLOCKED:GGEN_PACK_MISSING:{name}")


class GgenEnvironment:
    def __init__(self, *, source: Path, ggen_bin: str = "ggen", timeout_seconds: float = 5.0, max_files: int = _MAX_FILES_DEFAULT, max_bytes: int = _MAX_BYTES_DEFAULT) -> None:
        self.environment_id = f"urn:gymact:ggen:environment:{uuid4().hex}"
        self.requires_authority = True
        self._temp = tempfile.TemporaryDirectory(prefix="gymact-ggen-")
        self._root = Path(self._temp.name) / "project"
        shutil.copytree(source, self._root)
        self._ggen_bin = ggen_bin
        self._timeout = timeout_seconds
        self._max_files = max_files
        self._max_bytes = max_bytes
        self._closed = False

    @property
    def workspace(self) -> Path:
        return self._root

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("environment is torn down")

    def capabilities(self) -> tuple[Capability, ...]:
        self._ensure_open()
        return GGEN_CAPABILITIES

    async def observe(self) -> dict[str, Any]:
        self._ensure_open()
        return _snapshot(self._root, max_files=self._max_files, max_bytes=self._max_bytes)

    async def _run(self, *args: str) -> dict[str, Any]:
        try:
            process = await asyncio.create_subprocess_exec(self._ggen_bin, *args, cwd=self._root, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        except FileNotFoundError as exc:
            raise RuntimeError("BLOCKED:GGEN_BINARY_MISSING") from exc
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=self._timeout)
        except TimeoutError:
            process.kill()
            await process.communicate()
            raise RuntimeError("BLOCKED:GGEN_COMMAND_TIMEOUT")
        return {"returncode": process.returncode, "stdout": stdout.decode("utf-8", errors="replace")[-4000:], "stderr": stderr.decode("utf-8", errors="replace")[-4000:]}

    async def actuate(self, capability: Capability, payload: dict[str, Any]) -> dict[str, Any]:
        del payload
        self._ensure_open()
        before = await self.observe()
        commands = {"graph-validate": ("graph", "validate"), "doctor": ("doctor", "run"), "sync": ("sync", "run"), "receipt-verify": ("receipt", "verify")}
        args = commands.get(capability.binding)
        if args is None:
            raise ValueError(f"unsupported ggen binding: {capability.binding}")
        process = await self._run(*args)
        after = await self.observe()
        return {"before": before, "after": after, **process}

    async def verify(self, expected: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        observed = await self.observe()
        passed = all(observed.get(key) == value for key, value in expected.items())
        return passed, observed

    async def checkpoint(self) -> dict[str, Any]:
        self._ensure_open()
        files: dict[str, bytes] = {}
        for path in sorted(p for p in self._root.rglob("*") if p.is_file()):
            relative = path.relative_to(self._root)
            if any(part in _IGNORED_PARTS for part in relative.parts):
                continue
            files[relative.as_posix()] = path.read_bytes()
        _snapshot(self._root, max_files=self._max_files, max_bytes=self._max_bytes)
        return {"files": files}

    async def restore(self, checkpoint: dict[str, Any]) -> None:
        self._ensure_open()
        files = checkpoint.get("files")
        if not isinstance(files, dict) or not all(isinstance(path, str) and isinstance(data, bytes) for path, data in files.items()):
            raise TypeError("checkpoint.files must map path strings to bytes")
        shutil.rmtree(self._root)
        self._root.mkdir(parents=True)
        for relative, data in files.items():
            target = (self._root / relative).resolve()
            if self._root.resolve() not in target.parents and target != self._root.resolve():
                raise ValueError("REFUSED:GGEN_CHECKPOINT_PATH_TRAVERSAL")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        _snapshot(self._root, max_files=self._max_files, max_bytes=self._max_bytes)

    async def teardown(self) -> None:
        if not self._closed:
            self._temp.cleanup()
        self._closed = True


class GgenProvider:
    name = "ggen"
    materialization_requires_authority = False

    async def materialize(self, *, scenario: str | None, config: dict[str, Any]) -> GgenEnvironment:
        del scenario
        source_value = config.get("source")
        if not isinstance(source_value, str) or not source_value:
            raise TypeError("config.source must be a non-empty dependency-closed ggen consumer")
        source = Path(source_value).expanduser().resolve()
        if not source.is_dir():
            raise TypeError(f"config.source is not a directory: {source}")
        if not (source / "ggen.toml").is_file():
            raise TypeError("config.source must contain ggen.toml; a bare pack is not executable")
        _require_dependency_closed_consumer(source)
        ggen_bin = config.get("ggen_bin", "ggen")
        if not isinstance(ggen_bin, str) or not ggen_bin:
            raise TypeError("config.ggen_bin must be a non-empty string")
        timeout = config.get("timeout_seconds", 5.0)
        if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or timeout <= 0:
            raise TypeError("config.timeout_seconds must be positive")
        max_files = config.get("max_files", _MAX_FILES_DEFAULT)
        max_bytes = config.get("max_bytes", _MAX_BYTES_DEFAULT)
        if not isinstance(max_files, int) or max_files <= 0:
            raise TypeError("config.max_files must be a positive integer")
        if not isinstance(max_bytes, int) or max_bytes <= 0:
            raise TypeError("config.max_bytes must be a positive integer")
        return GgenEnvironment(source=source, ggen_bin=ggen_bin, timeout_seconds=float(timeout), max_files=max_files, max_bytes=max_bytes)
