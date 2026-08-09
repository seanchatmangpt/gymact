"""Bounded real-ggen gym.

The subject is the current ``ggen`` CLI. Materialization copies an admitted,
dependency-closed ggen consumer project plus its declared manifest dependencies
into a private temporary bundle. ``sync run`` can therefore never actuate the
caller's source checkout.
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
    Capability(
        iri="urn:gymact:ggen:capability:graph-validate",
        title="Validate the admitted ggen graph/templates",
        consequence=Consequence.READ,
        binding="graph-validate",
    ),
    Capability(
        iri="urn:gymact:ggen:capability:doctor",
        title="Inspect ggen project health",
        consequence=Consequence.READ,
        binding="doctor",
    ),
    Capability(
        iri="urn:gymact:ggen:capability:sync",
        title="Manufacture project projections with ggen sync run",
        consequence=Consequence.DO,
        binding="sync",
    ),
    Capability(
        iri="urn:gymact:ggen:capability:receipt-verify",
        title="Verify ggen's latest manufacturing receipt",
        consequence=Consequence.READ,
        binding="receipt-verify",
    ),
)

_IGNORED_PARTS = {".git", "__pycache__", ".pytest_cache", "target"}
_MAX_FILES_DEFAULT = 512
_MAX_BYTES_DEFAULT = 8 * 1024 * 1024


def _within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _declared_dependencies(source: Path, bundle_root: Path) -> tuple[Path, ...]:
    manifest = tomllib.loads((source / "ggen.toml").read_text(encoding="utf-8"))
    raw_paths: list[tuple[str, str]] = []

    ontology = manifest.get("ontology") or {}
    if isinstance(ontology, dict) and isinstance(ontology.get("source"), str):
        raw_paths.append(("ontology.source", ontology["source"]))

    templates = manifest.get("templates") or {}
    if isinstance(templates, dict) and isinstance(templates.get("dir"), str):
        raw_paths.append(("templates.dir", templates["dir"]))

    packs = manifest.get("packs") or {}
    if isinstance(packs, dict):
        for name, config in packs.items():
            if isinstance(config, dict) and isinstance(config.get("path"), str):
                raw_paths.append((f"packs.{name}.path", config["path"]))

    dependencies: list[Path] = []
    for field, raw in raw_paths:
        candidate = Path(raw)
        resolved = candidate.resolve() if candidate.is_absolute() else (source / candidate).resolve()
        if not _within(resolved, bundle_root):
            raise ValueError(f"REFUSED:GGEN_DEPENDENCY_OUTSIDE_BUNDLE:{field}")
        if not resolved.exists():
            raise ValueError(f"BLOCKED:GGEN_DEPENDENCY_MISSING:{field}")
        dependencies.append(resolved)
    return tuple(dict.fromkeys(dependencies))


def _iter_files(root: Path, bundle_root: Path):
    if root.is_symlink():
        resolved = root.resolve()
        if not _within(resolved, bundle_root):
            raise ValueError("REFUSED:GGEN_SYMLINK_OUTSIDE_BUNDLE")
    if root.is_file():
        yield root
        return
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if any(part in _IGNORED_PARTS for part in relative.parts):
            continue
        if path.is_symlink():
            resolved = path.resolve()
            if not _within(resolved, bundle_root):
                raise ValueError("REFUSED:GGEN_SYMLINK_OUTSIDE_BUNDLE")
        if path.is_file():
            yield path


def _preflight(
    roots: tuple[Path, ...],
    *,
    bundle_root: Path,
    max_files: int,
    max_bytes: int,
) -> None:
    seen: set[Path] = set()
    total_bytes = 0
    for root in roots:
        for path in _iter_files(root, bundle_root):
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            if len(seen) > max_files:
                raise RuntimeError("BLOCKED:GGEN_GYM_FILE_LIMIT")
            total_bytes += resolved.stat().st_size
            if total_bytes > max_bytes:
                raise RuntimeError("BLOCKED:GGEN_GYM_BYTE_LIMIT")


def _copy_into_bundle(source: Path, bundle_root: Path, destination_bundle: Path) -> Path:
    relative = source.relative_to(bundle_root)
    target = destination_bundle / relative
    if source.is_dir():
        shutil.copytree(source, target, dirs_exist_ok=True)
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    return target


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
        "files": [
            {"path": path, "sha256": content_digest, "bytes": size}
            for path, content_digest, size in records
        ],
    }


class GgenEnvironment:
    def __init__(
        self,
        *,
        source: Path,
        bundle_root: Path,
        dependencies: tuple[Path, ...],
        ggen_bin: str = "ggen",
        timeout_seconds: float = 5.0,
        max_files: int = _MAX_FILES_DEFAULT,
        max_bytes: int = _MAX_BYTES_DEFAULT,
    ) -> None:
        self.environment_id = f"urn:gymact:ggen:environment:{uuid4().hex}"
        self.requires_authority = True
        self._temp = tempfile.TemporaryDirectory(prefix="gymact-ggen-")
        self._bundle = Path(self._temp.name) / "bundle"
        self._bundle.mkdir()
        self._workspace_relative = source.relative_to(bundle_root)

        roots = tuple(dict.fromkeys((source, *dependencies)))
        _preflight(
            roots,
            bundle_root=bundle_root,
            max_files=max_files,
            max_bytes=max_bytes,
        )
        for root in roots:
            _copy_into_bundle(root, bundle_root, self._bundle)

        self._root = self._bundle / self._workspace_relative
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
        observed = _snapshot(
            self._bundle,
            max_files=self._max_files,
            max_bytes=self._max_bytes,
        )
        observed["workspace"] = self._workspace_relative.as_posix()
        observed["receipt_present"] = (
            self._root / ".ggen" / "receipts" / "latest.json"
        ).is_file()
        return observed

    async def _run(self, *args: str) -> dict[str, Any]:
        try:
            process = await asyncio.create_subprocess_exec(
                self._ggen_bin,
                *args,
                cwd=self._root,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError as exc:
            raise RuntimeError("BLOCKED:GGEN_BINARY_MISSING") from exc
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=self._timeout
            )
        except TimeoutError:
            process.kill()
            await process.communicate()
            raise RuntimeError("BLOCKED:GGEN_COMMAND_TIMEOUT")
        return {
            "returncode": process.returncode,
            "stdout": stdout.decode("utf-8", errors="replace")[-4000:],
            "stderr": stderr.decode("utf-8", errors="replace")[-4000:],
        }

    async def actuate(
        self, capability: Capability, payload: dict[str, Any]
    ) -> dict[str, Any]:
        del payload
        self._ensure_open()
        before = await self.observe()
        commands = {
            "graph-validate": ("graph", "validate"),
            "doctor": ("doctor", "run"),
            "sync": ("sync", "run"),
            "receipt-verify": ("receipt", "verify"),
        }
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
        for path in sorted(p for p in self._bundle.rglob("*") if p.is_file()):
            relative = path.relative_to(self._bundle)
            if any(part in _IGNORED_PARTS for part in relative.parts):
                continue
            files[relative.as_posix()] = path.read_bytes()
        _snapshot(
            self._bundle,
            max_files=self._max_files,
            max_bytes=self._max_bytes,
        )
        return {"files": files}

    async def restore(self, checkpoint: dict[str, Any]) -> None:
        self._ensure_open()
        files = checkpoint.get("files")
        if not isinstance(files, dict) or not all(
            isinstance(path, str) and isinstance(data, bytes)
            for path, data in files.items()
        ):
            raise TypeError("checkpoint.files must map path strings to bytes")
        shutil.rmtree(self._bundle)
        self._bundle.mkdir(parents=True)
        for relative, data in files.items():
            target = (self._bundle / relative).resolve()
            if not _within(target, self._bundle.resolve()):
                raise ValueError("REFUSED:GGEN_CHECKPOINT_PATH_TRAVERSAL")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        self._root = self._bundle / self._workspace_relative
        _snapshot(
            self._bundle,
            max_files=self._max_files,
            max_bytes=self._max_bytes,
        )

    async def teardown(self) -> None:
        if not self._closed:
            self._temp.cleanup()
        self._closed = True


class GgenProvider:
    name = "ggen"
    materialization_requires_authority = False

    async def materialize(
        self, *, scenario: str | None, config: dict[str, Any]
    ) -> GgenEnvironment:
        del scenario
        source_value = config.get("source")
        if not isinstance(source_value, str) or not source_value:
            raise TypeError(
                "config.source must be a non-empty ggen consumer project directory"
            )
        source = Path(source_value).expanduser().resolve()
        if not source.is_dir():
            raise TypeError(f"config.source is not a directory: {source}")
        if not (source / "ggen.toml").is_file():
            raise TypeError(
                "config.source must contain ggen.toml; a bare pack is not executable"
            )

        bundle_value = config.get("bundle_root", source_value)
        if not isinstance(bundle_value, str) or not bundle_value:
            raise TypeError("config.bundle_root must be a non-empty directory")
        bundle_root = Path(bundle_value).expanduser().resolve()
        if not bundle_root.is_dir():
            raise TypeError(f"config.bundle_root is not a directory: {bundle_root}")
        if not _within(source, bundle_root):
            raise ValueError("REFUSED:GGEN_SOURCE_OUTSIDE_BUNDLE")

        ggen_bin = config.get("ggen_bin", "ggen")
        if not isinstance(ggen_bin, str) or not ggen_bin:
            raise TypeError("config.ggen_bin must be a non-empty string")
        timeout = config.get("timeout_seconds", 5.0)
        if (
            not isinstance(timeout, (int, float))
            or isinstance(timeout, bool)
            or timeout <= 0
        ):
            raise TypeError("config.timeout_seconds must be positive")
        max_files = config.get("max_files", _MAX_FILES_DEFAULT)
        max_bytes = config.get("max_bytes", _MAX_BYTES_DEFAULT)
        if not isinstance(max_files, int) or max_files <= 0:
            raise TypeError("config.max_files must be a positive integer")
        if not isinstance(max_bytes, int) or max_bytes <= 0:
            raise TypeError("config.max_bytes must be a positive integer")

        dependencies = _declared_dependencies(source, bundle_root)
        return GgenEnvironment(
            source=source,
            bundle_root=bundle_root,
            dependencies=dependencies,
            ggen_bin=ggen_bin,
            timeout_seconds=float(timeout),
            max_files=max_files,
            max_bytes=max_bytes,
        )
