#!/usr/bin/env python3
"""Autonomous discovery-and-actuation loop: for each subject, probe its real
repo (via a real fastmcp round trip), ask a real local LLM (TurboFieldfare,
OpenAI-compatible endpoint) to propose a real, bounded subprocess command,
run it through `GenericDiscoveredProvider`, and write a real OCEL 2.0 log.

No per-subject Python is hand-written here -- the LLM supplies the recipe
(command/success markers), `GenericDiscoveredProvider` (gymact/gyms/
discovered.py) is the one execution path for all subjects. Standing is never
asserted by this script narratively -- it only writes the OCEL log; a
separate script (`ocel_standing.py`) is the sole source of standing claims,
per this session's OCEL-only-success-reporting requirement.

Usage:
    .venv/bin/python scripts/discover_and_actuate.py <slug>:<abs_path> [...]
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import fastmcp

from gymact import GymAct, MaterializationIntent
from gymact.gyms.discovered import GenericDiscoveredProvider
from gymact.models import ActuationIntent
from gymact.ocel import write_ocel_log
from gymact.surfaces.fastmcp import create_mcp

LLM_BASE_URL = "http://127.0.0.1:8080/v1"
LLM_MODEL = "gemma-4-26b-a4b-it"
REPORTS_DIR = Path(__file__).parent.parent / "reports" / "ocel"

RECIPE_SYSTEM_PROMPT = (
    "You are proposing ONE bounded, safe shell command to smoke-test whether "
    "a benchmark/gym repository is real and minimally runnable. You are NOT "
    "solving the benchmark's actual tasks -- you are proving the repository "
    "is importable/invocable. Prefer the fastest possible check: --help, "
    '--version, `python -c "import <top_level_package>"`, or a documented '
    "quickstart/smoke command from the README if one exists and is fast "
    "(no training, no GPU, no network installs beyond what's already vendored, "
    "no long-running servers). Never propose destructive commands (rm, sudo, "
    "curl|sh, git push, docker without a stop). Always use the exact "
    "executable name 'python3' (never bare 'python' -- it is not guaranteed "
    "to be on PATH; a missing executable and a real timeout are otherwise "
    "indistinguishable in the evidence). "
    "Respond with ONLY a JSON object, no prose, no markdown fences: "
    '{"command": ["<argv0>", "<arg1>", ...], "success_markers": ["<substring "'
    'that would appear in stdout on success, or empty list if unsure>"], '
    '"timeout_seconds": <number, 20-90, default 30 -- a cold Python interpreter '
    "start plus first-import module resolution can genuinely take 10-15s on its "
    "own, so do not propose less than 20 for any real import/subprocess check>, "
    '"reasoning": "<one sentence>"}'
)


def _is_llm_reachable() -> bool:
    try:
        with urllib.request.urlopen("http://127.0.0.1:8080/health", timeout=2) as resp:
            return resp.status == 200
    except OSError:
        return False


def _propose_recipe(subject: str, probe: dict) -> dict:
    """Real HTTP call to the real local TurboFieldfare server (OpenAI-compatible
    chat completions), asking for a real, structured actuation recipe."""
    user_content = json.dumps(
        {
            "subject": subject,
            "readme_excerpt": (probe.get("readme") or "")[:2500],
            "pyproject_toml_excerpt": (probe.get("pyproject_toml") or "")[:1200],
            "setup_py_excerpt": (probe.get("setup_py") or "")[:1200],
            "top_level_files": probe.get("top_level_files", []),
            "cwd": probe.get("subject_path"),
        }
    )
    payload = {
        "model": LLM_MODEL,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": RECIPE_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
    }
    request = urllib.request.Request(
        f"{LLM_BASE_URL}/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as resp:
        body = json.loads(resp.read())
    content = body["choices"][0]["message"]["content"]
    match = re.search(r"\{.*\}", content, re.DOTALL)
    if not match:
        raise ValueError(f"LLM did not return a JSON object: {content!r}")
    return json.loads(match.group(0))


async def _run_subject(slug: str, path: Path) -> None:
    server = create_mcp()
    async with fastmcp.Client(server) as client:
        probe_result = await client.call_tool("probe_repo", {"subject_path": str(path)})
        probe = probe_result.structured_content

    subject_dir = REPORTS_DIR / slug
    subject_dir.mkdir(parents=True, exist_ok=True)
    log_path = subject_dir / "episode.ocel.json"

    gym = GymAct()
    gym.register_provider(GenericDiscoveredProvider())
    receipts = []

    if not probe or not probe.get("exists"):
        m = await gym.materialize(
            MaterializationIntent(
                provider="discovered",
                config={
                    "subject": slug,
                    "command": ["true"],
                    "cwd": "/tmp",
                    "success_markers": [f"__gymact_absent_marker_{slug}__"],
                },
            )
        )
        receipts.append(m.receipt)
        if m.accepted:
            r = await gym.act(
                ActuationIntent(
                    episode_id=m.episode.episode_id,
                    capability="urn:gymact:discovered:capability:run",
                )
            )
            receipts.append(r.receipt)
            receipts.append(await gym.teardown(m.episode.episode_id))
        _log, digest = write_ocel_log(log_path, receipts)
        print(f"{slug}: repo not checked out -- {digest}")
        return

    # Hard floor, independent of the prompt guidance above: a real cold
    # interpreter start + first-import module resolution genuinely took
    # >10s for at least one subject during this session's first real batch
    # run (recorded as a real `subprocess.TimeoutExpired`, not a guess --
    # see smoke-lock.ttl's toolsandbox/r2e-gym history). A prompt nudge
    # alone is not a guarantee the LLM honors it, so enforce this in code.
    MIN_TIMEOUT_SECONDS = 20.0

    try:
        recipe = _propose_recipe(slug, probe)
        command = recipe["command"]
        success_markers = recipe.get("success_markers", [])
        timeout_seconds = max(MIN_TIMEOUT_SECONDS, float(recipe.get("timeout_seconds", 30)))
    except Exception as exc:
        recipe = None
        command = ["python3", "--version"]  # bounded, always-safe fallback
        success_markers = []
        timeout_seconds = MIN_TIMEOUT_SECONDS
        print(f"{slug}: LLM recipe failed ({exc}); using fallback probe", file=sys.stderr)

    m = await gym.materialize(
        MaterializationIntent(
            provider="discovered",
            config={
                "subject": slug,
                "command": command,
                "cwd": str(path),
                "timeout_seconds": timeout_seconds,
                "success_markers": success_markers,
            },
        )
    )
    receipts.append(m.receipt)

    if m.accepted:
        episode_id = m.episode.episode_id
        act_result = await gym.act(
            ActuationIntent(
                episode_id=episode_id, capability="urn:gymact:discovered:capability:run"
            )
        )
        # `receipt.standing == ALIVE` only means the actuation mechanism ran
        # without raising -- it does NOT mean the underlying command
        # succeeded/solved anything (a failed `import` is still a
        # successfully-executed subprocess). Attach the real observed
        # `solved`/`returncode` truth onto the receipt's own `reason` field
        # (the only free-text evidence channel `Receipt` carries) so the OCEL
        # log itself -- not this script's stdout -- carries that distinction.
        # Caught and fixed this session after `ocel_standing.py` initially
        # reported GYMACT_ACTUATED for subjects whose own import had failed.
        #
        # Second bug, caught on re-run: `returncode=None` is NOT unique to a
        # real timeout -- DiscoveredEnvironment.actuate()'s `except OSError`
        # branch (command literally not found, e.g. bare `python` when only
        # `python3` is on PATH) also leaves returncode=None, and previously
        # this reason string didn't carry `timed_out` or `stderr`, so a
        # command-not-found and a real timeout were indistinguishable from
        # the OCEL evidence alone. Both are now embedded explicitly.
        observed_state = act_result.observation.state if act_result.observation else {}
        stderr_snippet = (observed_state.get("stderr") or "")[:200]
        solved_marker = (
            f"solved={observed_state.get('solved')} "
            f"returncode={observed_state.get('returncode')} "
            f"timed_out={observed_state.get('timed_out')} "
            f"stderr={stderr_snippet!r}"
        )
        receipt_with_solved = act_result.receipt.model_copy(
            update={
                "reason": (
                    f"{act_result.receipt.reason}; {solved_marker}"
                    if act_result.receipt.reason
                    else solved_marker
                )
            }
        )
        receipts.append(receipt_with_solved)

        expected = {"solved": True} if success_markers else {}
        if expected:
            verification = await gym.verify(episode_id, expected)
            print(f"{slug}: command={command} verify_passed={verification.passed}")
        else:
            print(
                f"{slug}: command={command} "
                f"returncode={act_result.observation.state.get('returncode')}"
            )

        receipts.append(await gym.teardown(episode_id))

    log, digest = write_ocel_log(log_path, receipts)
    print(f"{slug}: {len(log['events'])} events, sha256={digest}")
    if recipe:
        (subject_dir / "recipe.json").write_text(json.dumps(recipe, indent=2))


async def main() -> None:
    subjects = []
    for arg in sys.argv[1:]:
        slug, _, path = arg.partition(":")
        subjects.append((slug, Path(path)))

    if not subjects:
        print("usage: discover_and_actuate.py <slug>:<abs_path> [...]", file=sys.stderr)
        sys.exit(2)

    if not _is_llm_reachable():
        print("REFUSED: no real LLM reachable at http://127.0.0.1:8080/health", file=sys.stderr)
        sys.exit(1)

    for slug, path in subjects:
        try:
            await _run_subject(slug, path)
        except Exception as exc:
            print(f"{slug}: driver error (not silently skipped): {exc}", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
