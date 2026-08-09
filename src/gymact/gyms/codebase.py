"""Isolated Git codebase gym with public software/supply-chain semantics.

The source checkout is observation input only. Materialization copies it into a
private temporary worktree; there is deliberately no push, merge, release, or
other remote Git capability.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any
from uuid import uuid4

from gymact.models import Capability, Consequence

CODEBASE_CAPABILITIES = (
    Capability(
        iri="urn:gymact:codebase:capability:inspect",
        title="Inspect isolated repository and SPDX/SWH identity",
        consequence=Consequence.READ,
        binding="inspect",
    ),
    Capability(
        iri="urn:gymact:codebase:capability:write-text",
        title="Write UTF-8 source text",
        consequence=Consequence.DO,
        binding="write_text",
    ),
    Capability(
        iri="urn:gymact:codebase:capability:apply-replacement",
        title="Apply one exact source replacement",
        consequence=Consequence.DO,
        binding="apply_replacement",
    ),
    Capability(
        iri="urn:gymact:codebase:capability:delete-file",
        title="Delete one source file",
        consequence=Consequence.DO,
        binding="delete_file",
    ),
    Capability(
        iri="urn:gymact:codebase:capability:run-build",
        title="Run admitted build command",
        consequence=Consequence.DO,
        binding="run_build",
    ),
    Capability(
        iri="urn:gymact:codebase:capability:run-test",
        title="Run admitted test command",
        consequence=Consequence.DO,
        binding="run_test",
    ),
    Capability(
        iri="urn:gymact:codebase:capability:run-lint",
        title="Run admitted lint command",
        consequence=Consequence.DO,
        binding="run_lint",
    ),
    Capability(
        iri="urn:gymact:codebase:capability:run-typecheck",
        title="Run admitted type-check command",
        consequence=Consequence.DO,
        binding="run_typecheck",
    ),
    Capability(
        iri="urn:gymact:codebase:capability:commit",
        title="Commit isolated worktree changes",
        consequence=Consequence.DO,
        binding="commit",
    ),
)

_MANIFESTS = {
    "Cargo.toml",
    "package.json",
    "pyproject.toml",
    "requirements.txt",
    "go.mod",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
}


def _partial_match(observed: object, expected: object) -> bool:
    if isinstance(expected, dict):
        return isinstance(observed, dict) and all(
            key in observed and _partial_match(observed[key], value)
            for key, value in expected.items()
        )
    return observed == expected


def _bounded(root: Path, relative: str) -> Path:
    if not relative or Path(relative).is_absolute():
        raise ValueError("AMBIGUOUS_SUBJECT_REFUSED")
    path = (root / relative).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError("AMBIGUOUS_SUBJECT_REFUSED") from exc
    return path


class CodebaseEnvironment:
    """Private disposable copy of one admitted Git checkout."""

    requires_authority = True

    def __init__(
        self,
        source: Path,
        root: Path,
        commands: dict[str, tuple[str, ...]],
        max_seconds: float,
    ) -> None:
        self.source = source.resolve()
        self.root = root.resolve()
        self.commands = commands
        self.max_seconds = max_seconds
        self.environment_id = f"urn:gymact:codebase:environment:{uuid4().hex}"
        self._closed = False

    def _open(self) -> None:
        if self._closed:
            raise RuntimeError("environment is torn down")

    def _git(self, *args: str, env: dict[str, str] | None = None) -> str:
        self._open()
        completed = subprocess.run(
            ["git", *args],
            cwd=self.root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=self.max_seconds,
            env=env,
        )
        if completed.returncode != 0:
            detail = completed.stderr.strip()[:300]
            raise RuntimeError(
                f"GIT_COMMAND_FAILED:{args[0]}:{completed.returncode}:{detail}"
            )
        return completed.stdout.strip()

    def capabilities(self) -> tuple[Capability, ...]:
        self._open()
        return CODEBASE_CAPABILITIES

    def _files(self) -> dict[str, dict[str, Any]]:
        files: dict[str, dict[str, Any]] = {}
        for path in sorted(item for item in self.root.rglob("*") if item.is_file()):
            relative = path.relative_to(self.root).as_posix()
            if relative.startswith(".git/"):
                continue
            data = path.read_bytes()
            blob = self._git("hash-object", "--", relative)
            files[relative] = {
                "sha256": hashlib.sha256(data).hexdigest(),
                "git_blob_sha1": blob,
                "swhid": f"swh:1:cnt:{blob}",
                "size": len(data),
            }
        return files

    def semantic_snapshot_turtle(self) -> str:
        """Project the exact Git snapshot into public software semantics.

        This is a GymAct application-profile view, not a private class hierarchy.
        SPDX 3 represents the repository snapshot/SBOM and content identities;
        Schema.org + DOAP describe the source project; PROV-O binds provenance.
        """

        head = self._git("rev-parse", "HEAD")
        tree = self._git("rev-parse", "HEAD^{tree}")
        repo_id = f"urn:gymact:codebase:repo:{head}"
        sbom_id = f"urn:gymact:codebase:sbom:{head}"
        lines = [
            "@prefix spdx: <https://spdx.org/rdf/3.0.1/terms/Software/> .",
            "@prefix core: <https://spdx.org/rdf/3.0.1/terms/Core/> .",
            "@prefix schema: <https://schema.org/> .",
            "@prefix doap: <http://usefulinc.com/ns/doap#> .",
            "@prefix prov: <http://www.w3.org/ns/prov#> .",
            "@prefix dct: <http://purl.org/dc/terms/> .",
            "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .",
            "",
            (
                f"<{repo_id}> a spdx:Package, schema:SoftwareSourceCode, "
                "doap:Project, prov:Entity ;"
            ),
            f"  core:spdxId {json.dumps(repo_id)}^^xsd:anyURI ;",
            f"  core:name {json.dumps('git-snapshot-' + head[:12])} ;",
            f"  dct:identifier {json.dumps(head)} ;",
            f"  spdx:sourceInfo {json.dumps('isolated Git snapshot; tree=' + tree)} ;",
            f"  spdx:contentIdentifier <urn:gymact:codebase:cid:revision:{head}> .",
            f"<urn:gymact:codebase:cid:revision:{head}> a spdx:ContentIdentifier ;",
            (
                "  spdx:contentIdentifierType "
                "<https://spdx.org/rdf/3.0.1/terms/Software/"
                "ContentIdentifierType/swhid> ;"
            ),
            (
                "  spdx:contentIdentifierValue "
                f"{json.dumps('swh:1:rev:' + head)}^^xsd:anyURI ."
            ),
        ]
        file_ids: list[str] = []
        for index, (relative, metadata) in enumerate(self._files().items()):
            file_id = f"urn:gymact:codebase:file:{head}:{index}"
            file_ids.append(file_id)
            lines += [
                f"<{file_id}> a spdx:File, prov:Entity ;",
                f"  core:spdxId {json.dumps(file_id)}^^xsd:anyURI ;",
                f"  core:name {json.dumps(relative)} ;",
                (
                    "  spdx:contentIdentifier "
                    f"<urn:gymact:codebase:cid:file:{head}:{index}> ;"
                ),
                f"  prov:specializationOf <{repo_id}> .",
                (
                    f"<urn:gymact:codebase:cid:file:{head}:{index}> "
                    "a spdx:ContentIdentifier ;"
                ),
                (
                    "  spdx:contentIdentifierType "
                    "<https://spdx.org/rdf/3.0.1/terms/Software/"
                    "ContentIdentifierType/swhid> ;"
                ),
                (
                    "  spdx:contentIdentifierValue "
                    f"{json.dumps(metadata['swhid'])}^^xsd:anyURI ."
                ),
            ]
        lines += [
            f"<{sbom_id}> a spdx:Sbom, prov:Bundle ;",
            f"  core:spdxId {json.dumps(sbom_id)}^^xsd:anyURI ;",
            f"  core:name {json.dumps('source-sbom-' + head[:12])} ;",
            (
                "  spdx:sbomType "
                "<https://spdx.org/rdf/3.0.1/terms/Software/SbomType/source> ;"
            ),
            f"  core:rootElement <{repo_id}>" + (" ;" if file_ids else " ."),
        ]
        if file_ids:
            members = ", ".join(
                f"<{value}>" for value in [repo_id, *file_ids]
            )
            lines.append(f"  core:element {members} .")
        return "\n".join(lines) + "\n"

    async def observe(self) -> dict[str, Any]:
        files = self._files()
        return {
            "head": self._git("rev-parse", "HEAD"),
            "tree": self._git("rev-parse", "HEAD^{tree}"),
            "branch": self._git("branch", "--show-current"),
            "status": self._git("status", "--porcelain=v1"),
            "files": files,
            "manifests": sorted(
                path for path in files if Path(path).name in _MANIFESTS
            ),
            "semantic_snapshot": self.semantic_snapshot_turtle(),
        }

    def _run(self, name: str) -> dict[str, Any]:
        argv = self.commands.get(name)
        if argv is None:
            raise ValueError(f"UNSUPPORTED:CODEBASE_COMMAND_NOT_ADMITTED:{name}")
        completed = subprocess.run(
            list(argv),
            cwd=self.root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=self.max_seconds,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
        return {
            "command": name,
            "argv": list(argv),
            "exit": completed.returncode,
            "stdout": completed.stdout[-4000:],
            "stderr": completed.stderr[-4000:],
        }

    async def actuate(
        self, capability: Capability, payload: dict[str, Any]
    ) -> dict[str, Any]:
        binding = capability.binding
        if binding == "write_text":
            path = _bounded(self.root, str(payload.get("path", "")))
            text = payload.get("text")
            if not isinstance(text, str):
                raise TypeError("write_text requires string text")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            return {"path": path.relative_to(self.root).as_posix(), "written": True}
        if binding == "apply_replacement":
            path = _bounded(self.root, str(payload.get("path", "")))
            before, after = payload.get("before"), payload.get("after")
            if not isinstance(before, str) or not isinstance(after, str):
                raise TypeError("apply_replacement requires string before/after")
            text = path.read_text(encoding="utf-8")
            if text.count(before) != 1:
                raise ValueError("REFUSED:REPLACEMENT_NOT_UNIQUE")
            path.write_text(text.replace(before, after, 1), encoding="utf-8")
            return {
                "path": path.relative_to(self.root).as_posix(),
                "replacements": 1,
            }
        if binding == "delete_file":
            path = _bounded(self.root, str(payload.get("path", "")))
            if path.exists() and not path.is_file():
                raise ValueError("REFUSED:DELETE_NON_FILE")
            existed = path.is_file()
            if existed:
                path.unlink()
            return {"path": path.relative_to(self.root).as_posix(), "deleted": existed}
        if binding.startswith("run_"):
            return self._run(binding.removeprefix("run_"))
        if binding == "commit":
            message = payload.get("message")
            if not isinstance(message, str) or not message.strip():
                raise ValueError("commit requires message")
            if not self._git("status", "--porcelain=v1"):
                raise ValueError("REFUSED:NO_CHANGES_TO_COMMIT")
            self._git("add", "--all")
            env = {
                **os.environ,
                "GIT_AUTHOR_NAME": "GymAct",
                "GIT_AUTHOR_EMAIL": "gymact@example.invalid",
                "GIT_COMMITTER_NAME": "GymAct",
                "GIT_COMMITTER_EMAIL": "gymact@example.invalid",
            }
            self._git("commit", "-m", message, env=env)
            return {
                "head": self._git("rev-parse", "HEAD"),
                "tree": self._git("rev-parse", "HEAD^{tree}"),
            }
        raise ValueError(f"unsupported provider binding: {binding}")

    async def verify(self, expected: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        observed = await self.observe()
        return _partial_match(observed, expected), observed

    async def checkpoint(self) -> dict[str, Any]:
        if self._git("status", "--porcelain=v1"):
            raise RuntimeError("checkpoint requires clean work tree")
        return {
            "head": self._git("rev-parse", "HEAD"),
            "branch": self._git("branch", "--show-current"),
        }

    async def restore(self, checkpoint: dict[str, Any]) -> None:
        head = checkpoint.get("head")
        if not isinstance(head, str) or not head:
            raise TypeError("checkpoint.head must be a revision")
        self._git("reset", "--hard", head)
        self._git("clean", "-fd")

    async def teardown(self) -> None:
        if not self._closed:
            self._closed = True
            shutil.rmtree(self.root.parent, ignore_errors=True)


class CodebaseProvider:
    name = "codebase"
    materialization_requires_authority = False

    async def materialize(
        self, *, scenario: str | None, config: dict[str, Any]
    ) -> CodebaseEnvironment:
        del scenario
        raw = config.get("root")
        if not isinstance(raw, str) or not raw:
            raise ValueError("PROVIDER_CONFIGURATION_REQUIRED")
        source = Path(raw).expanduser().resolve()
        if not source.is_dir() or not (source / ".git").exists():
            raise ValueError("PROVIDER_CONFIGURATION_REQUIRED")

        raw_commands = config.get("commands", {})
        if not isinstance(raw_commands, dict):
            raise TypeError("config.commands must be an object")
        commands: dict[str, tuple[str, ...]] = {}
        for name in ("build", "test", "lint", "typecheck"):
            argv = raw_commands.get(name)
            if argv is None:
                continue
            if (
                not isinstance(argv, list)
                or not argv
                or not all(isinstance(item, str) and item for item in argv)
            ):
                raise TypeError(
                    f"config.commands.{name} must be a non-empty string list"
                )
            commands[name] = tuple(argv)

        max_seconds = float(config.get("max_seconds", 30.0))
        if not 0 < max_seconds <= 120:
            raise ValueError("PROVIDER_CONFIGURATION_REQUIRED")

        parent = Path(tempfile.mkdtemp(prefix="gymact-codebase-"))
        worktree = parent / "repo"
        try:
            shutil.copytree(source, worktree, symlinks=True)
            return CodebaseEnvironment(source, worktree, commands, max_seconds)
        except Exception:
            shutil.rmtree(parent, ignore_errors=True)
            raise
