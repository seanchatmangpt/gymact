# Known Facts — Read Before Re-Deriving

Standing-facts file for gymact. Purpose: stop paying the cost of re-probing
environment constraints, roster state, and repo conventions every session
when they were already established (and, in at least one case, the
re-probe itself caused a real regression). Read this before running any
cluster-provisioning command, restating roster numbers, or re-deriving a
git-workflow convention from commit-message archaeology.

Each entry: dated, one line of claim, one pointer to where to verify it
directly if you need more than the summary. If a fact looks stale, verify
against its pointer and correct the entry in the same pass — don't just
work around it silently.

## Environment

- **2026-08-13** — `tests/test_kubernetes_reconciliation.py` and
  `tests/test_algebra_protocols.py`'s Kubernetes case both gate on a real
  reachability probe (`kubectl cluster-info`, 10s timeout) via
  `require_standing`/`pytest.skip`, never by provisioning or tearing down a
  cluster themselves. There is no `kind delete` call anywhere in this
  repo's own source (`grep -rn "kind delete" --include="*.py" .` → empty,
  confirmed this session). If a local `kind`/`k3d`/`colima --kubernetes`
  cluster is already running and reachable, the Kubernetes-reconciliation
  gym tests use it directly — do not delete and recreate a cluster to
  "refresh" it before running these tests; a missing/unreachable cluster
  already produces a named, visible skip, not a hang or false failure.
  Verify: `tests/test_kubernetes_reconciliation.py:31-56`
  (`_real_cluster_reachable`), `tests/test_algebra_protocols.py`'s
  `_kubernetes_cluster_reachable`.
- **2026-08-13** — CI provisions its own real kind cluster per-run via
  `helm/kind-action@v1` (`.github/workflows/ci.yml`, "Provision real
  kubectl + kind cluster" step) — this is a fresh ephemeral cluster on the
  GitHub-hosted runner, unrelated to any local dev-machine cluster. Don't
  conflate "CI recreates its cluster every run" with "local dev clusters
  should be recreated too."

## Repository conventions

- **2026-08-13** — Git workflow: direct commits to `main` are the current,
  real, accepted convention for solo/agent iteration in this repo (this
  repo is private, `gh api repos/.../branches/main/protection` returns 403
  — there is no branch-protection enforcement to target even if a stricter
  policy were declared). Branch-per-task (`agent/*`, `feat/*`) and
  `git worktree` remain available and are fine to use when isolation is
  wanted, but are not required. Do not re-derive this from grepping old
  commit messages — it's stated directly. Source: `CLAUDE.md`, "## Git
  workflow" section.
- **2026-08-13** — Whether a gym is actuated (not just importable, not just
  "its own pytest suite passes") is decided only by a real, schema-valid,
  conformant-replay, `solved=True` OCEL 2.0 log at
  `reports/ocel/<subject>/episode.ocel.json`, checked directly per
  `.claude/rules/ocel-standing.md` — never by a hardcoded expected value or
  a summarizing script's packaged verdict. Source: `CLAUDE.md`, "Evidence
  and standing" section.

## How to use this file

Before re-probing an environment constraint, re-deriving a roster/count
claim, or re-establishing a repo convention from history, check this file
first. If what you need isn't here, do the real investigation, then add a
dated entry so the next session doesn't pay the same cost.
