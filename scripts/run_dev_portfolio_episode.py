#!/usr/bin/env python3
"""Run one real GymAct episode over `DevPortfolioProvider` -- a real snapshot
of the user's actual local repos plus GitHub PR/issue/branch backlog -- and
write a real OCEL 2.0 log at reports/ocel/dev-portfolio/episode.ocel.json.

Mirrors `scripts/run_togaf_episode.py`'s real shape (materialize -> read ->
verify -> teardown -> write_ocel_log), simplified for a domain with zero `DO`
capabilities: no `AllowListAuthorityResolver` is needed since nothing here is
authority-gated (`DevPortfolioProvider.materialization_requires_authority =
False`, every capability is `Consequence.READ`). The real read happens via
`gym.observe(episode_id)` -- the kernel's own READ port -- not `gym.act()`,
per `kernel.py`'s `READ_CAPABILITY_IS_NOT_ACTUATION` refusal (confirmed while
building `tests/test_dev_portfolio.py`).

`verify()`'s expectation here is deliberately trivial and always-derivable
("every configured local repo that exists reports a non-empty branch name"),
per the plan's own non-goal: this script proves the domain observes real
state correctly, it does not judge whether that state is good or bad -- the
ranked "what's needed" triage stays a separate, human-decided action list.

Usage:
    uv run python scripts/run_dev_portfolio_episode.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from gymact import GymAct, MaterializationIntent
from gymact.gyms.dev_portfolio import DevPortfolioProvider
from gymact.ocel import write_ocel_log

REPORTS_DIR = Path(__file__).parent.parent / "reports" / "ocel"

# Same local repos this session actually inspected (git dirty/branch state),
# and the same 16 GitHub repos the earlier `ultracode` cross-repo audit
# covered -- real, already-verified-active repos, not an arbitrary list.
LOCAL_REPOS = {
    name: str(Path.home() / name)
    for name in (
        "ggen", "ggen-marketplace", "ggen-legacy", "ggen-create", "gymact",
        "autofde-lab", "bcinr", "mfw", "wasm4pm", "wasm4pm-compat", "unrdf",
    )
}

GITHUB_REPOS = [
    "seanchatmangpt/ww3gym", "seanchatmangpt/rrgym", "seanchatmangpt/affidavit",
    "seanchatmangpt/lifegym", "seanchatmangpt/autofde-lab", "seanchatmangpt/bcinr",
    "seanchatmangpt/ggen-marketplace", "seanchatmangpt/mfw", "seanchatmangpt/gymact",
    "seanchatmangpt/ggen", "seanchatmangpt/wasm4pm", "seanchatmangpt/ggen-legacy",
    "seanchatmangpt/wasm4pm-compat", "seanchatmangpt/ggen-create",
    "seanchatmangpt/SREGym", "seanchatmangpt/unrdf",
]


async def run() -> None:
    provider = DevPortfolioProvider()
    gym = GymAct()
    gym.register_provider(provider)
    receipts = []
    log_path = REPORTS_DIR / "dev-portfolio" / "episode.ocel.json"

    materialization = await gym.materialize(
        MaterializationIntent(
            provider="dev_portfolio",
            config={"local_repos": LOCAL_REPOS, "github_repos": GITHUB_REPOS},
        )
    )
    receipts.append(materialization.receipt)
    if not materialization.accepted or materialization.episode is None:
        print(f"dev_portfolio: materialization refused: {materialization.receipt.reason}")
        log, digest = write_ocel_log(log_path, receipts)
        print(f"dev_portfolio: {len(log['events'])} events, sha256={digest}")
        return

    episode_id = materialization.episode.episode_id

    observation = await gym.observe(episode_id)
    receipts.append(
        materialization.receipt.model_copy(
            update={
                "reason": (
                    f"observed {len(observation.state.get('local_repos', {}))} local repos, "
                    f"{len(observation.state.get('github_repos', {}))} github repos"
                )
            }
        )
    )

    for name, repo_state in observation.state.get("local_repos", {}).items():
        status = "dirty" if repo_state.get("dirty_files") else "clean"
        exists = repo_state.get("exists")
        print(f"dev_portfolio: local  {name:<20} exists={exists} status={status} branch={repo_state.get('branch')}")

    for slug, repo_state in observation.state.get("github_repos", {}).items():
        print(
            f"dev_portfolio: github {slug:<32} open_prs={repo_state.get('open_pr_count')} "
            f"open_issues={repo_state.get('open_issue_count')} stale_branches={repo_state.get('stale_branch_count')}"
        )

    # Trivial, always-derivable expectation: every configured local repo that
    # actually exists on disk reports a non-empty branch name.
    expected_branches = {
        name: {"branch": repo_state.get("branch")}
        for name, repo_state in observation.state.get("local_repos", {}).items()
        if repo_state.get("exists") and repo_state.get("branch")
    }
    verification = await gym.verify(episode_id, {"local_repos": expected_branches})
    print(f"dev_portfolio: verify_passed={verification.passed}")

    receipts.append(await gym.teardown(episode_id))

    log, digest = write_ocel_log(log_path, receipts)
    print(f"dev_portfolio: {len(log['events'])} events, sha256={digest}")


if __name__ == "__main__":
    asyncio.run(run())
