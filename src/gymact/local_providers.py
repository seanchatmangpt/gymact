"""Real local provider families used by the GymAct Crown conformance ladder.

These providers intentionally use bounded host primitives rather than mocks:
filesystem state, the installed Git executable, and Python's SQLite engine.
They preserve provider-specific physics behind the existing Environment SPI.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
from contextlib import closing
from pathlib import Path
from typing import Any
from uuid import uuid4

from gymact.models import Capability, Consequence


def _partial_match(observed: object, expected: object) -> bool:
    if isinstance(expected, dict):
        return isinstance(observed, dict) and all(
            key in observed and _partial_match(observed[key], value)
            for key, value in expected.items()
        )
    return observed == expected


def _bounded_path(root: Path, relative: str) -> Path:
    if not relative or Path(relative).is_absolute():
        raise ValueError("AMBIGUOUS_SUBJECT_REFUSED")
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError("AMBIGUOUS_SUBJECT_REFUSED") from exc
    return candidate


FILESYSTEM_CAPABILITIES = (
    Capability(
        iri="urn:gymact:filesystem:capability:write-text",
        title="Write UTF-8 text inside an admitted filesystem root",
        consequence=Consequence.DO,
        binding="write_text",
    ),
    Capability(
        iri="urn:gymact:filesystem:capability:delete",
        title="Delete a file inside an admitted filesystem root",
        consequence=Consequence.DO,
        binding="delete",
    ),
)


class FilesystemEnvironment:
    requires_authority = True

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.environment_id = f"urn:gymact:filesystem:environment:{uuid4().hex}"
        self._closed = False

    def _open(self) -> None:
        if self._closed:
            raise RuntimeError("environment is torn down")

    def capabilities(self) -> tuple[Capability, ...]:
        self._open()
        return FILESYSTEM_CAPABILITIES

    async def observe(self) -> dict[str, Any]:
        self._open()
        files: dict[str, dict[str, Any]] = {}
        for path in sorted(item for item in self.root.rglob("*") if item.is_file()):
            data = path.read_bytes()
            files[path.relative_to(self.root).as_posix()] = {
                "sha256": hashlib.sha256(data).hexdigest(),
                "size": len(data),
            }
        return {"root": str(self.root), "files": files}

    async def actuate(self, capability: Capability, payload: dict[str, Any]) -> dict[str, Any]:
        self._open()
        path = _bounded_path(self.root, str(payload.get("path", "")))
        if capability.binding == "write_text":
            text = payload.get("text")
            if not isinstance(text, str):
                raise TypeError("write_text requires string text")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            return {"path": path.relative_to(self.root).as_posix(), "written": True}
        if capability.binding == "delete":
            existed = path.is_file()
            if existed:
                path.unlink()
            return {"path": path.relative_to(self.root).as_posix(), "deleted": existed}
        raise ValueError(f"unsupported provider binding: {capability.binding}")

    async def verify(self, expected: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        observed = await self.observe()
        return _partial_match(observed, expected), observed

    async def checkpoint(self) -> dict[str, Any]:
        self._open()
        return {
            "files": {
                path.relative_to(self.root).as_posix(): path.read_text(encoding="utf-8")
                for path in sorted(item for item in self.root.rglob("*") if item.is_file())
            }
        }

    async def restore(self, checkpoint: dict[str, Any]) -> None:
        self._open()
        for path in sorted(
            (item for item in self.root.rglob("*") if item.is_file()), reverse=True
        ):
            path.unlink()
        files = checkpoint.get("files", {})
        if not isinstance(files, dict):
            raise TypeError("checkpoint.files must be an object")
        for relative, text in files.items():
            target = _bounded_path(self.root, str(relative))
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(str(text), encoding="utf-8")

    async def teardown(self) -> None:
        self._closed = True


class FilesystemProvider:
    name = "filesystem"
    materialization_requires_authority = False

    async def materialize(
        self, *, scenario: str | None, config: dict[str, Any]
    ) -> FilesystemEnvironment:
        del scenario
        root = Path(str(config.get("root", ""))).expanduser().resolve()
        if not root.is_dir():
            raise ValueError("PROVIDER_CONFIGURATION_REQUIRED")
        return FilesystemEnvironment(root)


GIT_CAPABILITIES = (
    Capability(
        iri="urn:gymact:git:capability:create-branch",
        title="Create and switch to a purpose branch",
        consequence=Consequence.DO,
        binding="create_branch",
    ),
    Capability(
        iri="urn:gymact:git:capability:write-text",
        title="Write UTF-8 text in a Git work tree",
        consequence=Consequence.DO,
        binding="write_text",
    ),
    Capability(
        iri="urn:gymact:git:capability:commit",
        title="Commit staged work-tree changes",
        consequence=Consequence.DO,
        binding="commit",
    ),
)


class GitEnvironment:
    requires_authority = True

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.environment_id = f"urn:gymact:git:environment:{uuid4().hex}"
        self._closed = False

    def _open(self) -> None:
        if self._closed:
            raise RuntimeError("environment is torn down")

    def _git(self, *args: str) -> str:
        self._open()
        completed = subprocess.run(
            ["git", *args],
            cwd=self.root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(f"git command failed:{args[0]}:{completed.returncode}")
        return completed.stdout.strip()

    def capabilities(self) -> tuple[Capability, ...]:
        self._open()
        return GIT_CAPABILITIES

    async def observe(self) -> dict[str, Any]:
        return {
            "root": str(self.root),
            "head": self._git("rev-parse", "HEAD"),
            "branch": self._git("branch", "--show-current"),
            "status": self._git("status", "--porcelain=v1"),
        }

    async def actuate(self, capability: Capability, payload: dict[str, Any]) -> dict[str, Any]:
        if capability.binding == "create_branch":
            name = payload.get("name")
            expected_revision = payload.get("expected_revision")
            if not isinstance(name, str) or not name or name.startswith("-"):
                raise ValueError("AMBIGUOUS_SUBJECT_REFUSED")
            current = self._git("rev-parse", "HEAD")
            if expected_revision is not None and expected_revision != current:
                raise ValueError("REVISION_MISMATCH_REFUSED")
            self._git("switch", "-c", name)
            return {"branch": name, "base_revision": current}
        if capability.binding == "write_text":
            path = _bounded_path(self.root, str(payload.get("path", "")))
            text = payload.get("text")
            if not isinstance(text, str):
                raise TypeError("write_text requires string text")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            return {"path": path.relative_to(self.root).as_posix(), "written": True}
        if capability.binding == "commit":
            message = payload.get("message")
            if not isinstance(message, str) or not message.strip():
                raise ValueError("commit requires message")
            self._git("add", "--all")
            self._git("commit", "-m", message)
            return {"head": self._git("rev-parse", "HEAD")}
        raise ValueError(f"unsupported provider binding: {capability.binding}")

    async def verify(self, expected: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        observed = await self.observe()
        return _partial_match(observed, expected), observed

    async def checkpoint(self) -> dict[str, Any]:
        observed = await self.observe()
        if observed["status"]:
            raise RuntimeError("checkpoint requires clean work tree")
        return {"head": observed["head"], "branch": observed["branch"]}

    async def restore(self, checkpoint: dict[str, Any]) -> None:
        head = checkpoint.get("head")
        if not isinstance(head, str) or not head:
            raise TypeError("checkpoint.head must be a revision")
        self._git("reset", "--hard", head)

    async def teardown(self) -> None:
        self._closed = True


class GitProvider:
    name = "git"
    materialization_requires_authority = False

    async def materialize(self, *, scenario: str | None, config: dict[str, Any]) -> GitEnvironment:
        del scenario
        root = Path(str(config.get("root", ""))).expanduser().resolve()
        if not root.is_dir() or not (root / ".git").exists():
            raise ValueError("PROVIDER_CONFIGURATION_REQUIRED")
        completed = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if completed.returncode != 0 or completed.stdout.strip() != "true":
            raise ValueError("PROVIDER_CONFIGURATION_REQUIRED")
        return GitEnvironment(root)


SQLITE_CAPABILITIES = (
    Capability(
        iri="urn:gymact:sqlite:capability:set",
        title="Set one JSON value in the bounded SQLite key-value table",
        consequence=Consequence.DO,
        binding="set",
    ),
    Capability(
        iri="urn:gymact:sqlite:capability:delete",
        title="Delete one value from the bounded SQLite key-value table",
        consequence=Consequence.DO,
        binding="delete",
    ),
)


class SQLiteEnvironment:
    requires_authority = True

    def __init__(self, database: Path) -> None:
        self.database = database.resolve()
        self.environment_id = f"urn:gymact:sqlite:environment:{uuid4().hex}"
        self._closed = False
        with closing(sqlite3.connect(self.database)) as connection, connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS gymact_state "
                "(key TEXT PRIMARY KEY, value_json TEXT NOT NULL)"
            )

    def _open(self) -> None:
        if self._closed:
            raise RuntimeError("environment is torn down")

    def capabilities(self) -> tuple[Capability, ...]:
        self._open()
        return SQLITE_CAPABILITIES

    async def observe(self) -> dict[str, Any]:
        self._open()
        with closing(sqlite3.connect(self.database)) as connection, connection:
            rows = connection.execute(
                "SELECT key, value_json FROM gymact_state ORDER BY key"
            ).fetchall()
        return {
            "database": str(self.database),
            "values": {key: json.loads(value) for key, value in rows},
        }

    async def actuate(self, capability: Capability, payload: dict[str, Any]) -> dict[str, Any]:
        self._open()
        key = payload.get("key")
        if not isinstance(key, str) or not key:
            raise ValueError("AMBIGUOUS_SUBJECT_REFUSED")
        with closing(sqlite3.connect(self.database)) as connection, connection:
            if capability.binding == "set":
                encoded = json.dumps(
                    payload.get("value"), sort_keys=True, separators=(",", ":")
                )
                connection.execute(
                    "INSERT INTO gymact_state(key, value_json) VALUES(?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json",
                    (key, encoded),
                )
                return {"key": key, "written": True}
            if capability.binding == "delete":
                cursor = connection.execute("DELETE FROM gymact_state WHERE key = ?", (key,))
                return {"key": key, "deleted": cursor.rowcount > 0}
        raise ValueError(f"unsupported provider binding: {capability.binding}")

    async def verify(self, expected: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        observed = await self.observe()
        return _partial_match(observed, expected), observed

    async def checkpoint(self) -> dict[str, Any]:
        observed = await self.observe()
        return {"values": observed["values"]}

    async def restore(self, checkpoint: dict[str, Any]) -> None:
        values = checkpoint.get("values")
        if not isinstance(values, dict):
            raise TypeError("checkpoint.values must be an object")
        with closing(sqlite3.connect(self.database)) as connection, connection:
            connection.execute("DELETE FROM gymact_state")
            connection.executemany(
                "INSERT INTO gymact_state(key, value_json) VALUES(?, ?)",
                [
                    (key, json.dumps(value, sort_keys=True, separators=(",", ":")))
                    for key, value in sorted(values.items())
                ],
            )

    async def teardown(self) -> None:
        self._closed = True


class SQLiteProvider:
    name = "sqlite"
    materialization_requires_authority = True

    async def materialize(
        self, *, scenario: str | None, config: dict[str, Any]
    ) -> SQLiteEnvironment:
        del scenario
        raw = config.get("database")
        if not isinstance(raw, str) or not raw:
            raise ValueError("PROVIDER_CONFIGURATION_REQUIRED")
        database = Path(raw).expanduser().resolve()
        if not database.parent.is_dir():
            raise ValueError("PROVIDER_CONFIGURATION_REQUIRED")
        return SQLiteEnvironment(database)
