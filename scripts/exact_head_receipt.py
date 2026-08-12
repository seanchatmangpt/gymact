#!/usr/bin/env python3
"""Emit or verify a transport-independent exact-head Git receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

SCHEMA = "urn:gymact:exact-head-receipt:v1"


class ReceiptRefused(RuntimeError):
    pass


def _git(repo: Path, *args: str) -> bytes:
    process = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if process.returncode != 0:
        detail = process.stderr.decode("utf-8", errors="replace").strip()
        raise ReceiptRefused(f"REFUSED:GIT_COMMAND:{' '.join(args)}:{detail}")
    return process.stdout


def _require_clean_tracked(repo: Path) -> None:
    process = subprocess.run(
        ["git", "diff", "--quiet", "HEAD", "--"],
        cwd=repo,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if process.returncode == 1:
        raise ReceiptRefused("REFUSED:TRACKED_WORKTREE_DIRTY")
    if process.returncode != 0:
        detail = process.stderr.decode("utf-8", errors="replace").strip()
        raise ReceiptRefused(f"REFUSED:GIT_DIFF:{detail}")


def observe(repo: Path, *, transport: str = "git-object-db") -> dict[str, Any]:
    _require_clean_tracked(repo)
    subject_sha = _git(repo, "rev-parse", "HEAD").decode().strip()
    tree_sha = _git(repo, "rev-parse", "HEAD^{tree}").decode().strip()
    manifest = _git(repo, "ls-tree", "-r", "--full-tree", "HEAD")
    return {
        "schema": SCHEMA,
        "subject_sha": subject_sha,
        "tree_sha": tree_sha,
        "tracked_manifest_sha256": hashlib.sha256(manifest).hexdigest(),
        "tracked_manifest_bytes": len(manifest),
        "transport": transport,
        "clean_tracked_worktree": True,
    }


def emit(
    repo: Path,
    *,
    expected_sha: str | None = None,
    transport: str = "git-object-db",
) -> dict[str, Any]:
    receipt = observe(repo, transport=transport)
    if expected_sha is not None and receipt["subject_sha"] != expected_sha:
        raise ReceiptRefused(
            f"REFUSED:EXACT_HEAD_MISMATCH:expected={expected_sha}:"
            f"observed={receipt['subject_sha']}"
        )
    return receipt


def verify(repo: Path, receipt: dict[str, Any]) -> dict[str, Any]:
    if receipt.get("schema") != SCHEMA:
        raise ReceiptRefused("REFUSED:EXACT_HEAD_RECEIPT_SCHEMA")
    observed = observe(repo, transport=str(receipt.get("transport", "git-object-db")))
    for field in (
        "subject_sha",
        "tree_sha",
        "tracked_manifest_sha256",
        "tracked_manifest_bytes",
        "clean_tracked_worktree",
    ):
        if receipt.get(field) != observed[field]:
            raise ReceiptRefused(
                f"REFUSED:EXACT_HEAD_RECEIPT_DRIFT:{field}:"
                f"expected={receipt.get(field)}:observed={observed[field]}"
            )
    return observed


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--expected-sha")
    parser.add_argument("--transport", default="git-object-db")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verify", type=Path)
    return parser


def main() -> int:
    args = _parser().parse_args()
    repo = args.repo.resolve()
    try:
        if args.verify is not None:
            stored = json.loads(args.verify.read_text(encoding="utf-8"))
            receipt = verify(repo, stored)
        else:
            receipt = emit(
                repo,
                expected_sha=args.expected_sha,
                transport=args.transport,
            )
        encoded = json.dumps(receipt, sort_keys=True, separators=(",", ":"))
        if args.output is not None:
            args.output.write_text(encoded + "\n", encoding="utf-8")
        print(encoded)
        return 0
    except (ReceiptRefused, OSError, json.JSONDecodeError) as exc:
        print(str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
