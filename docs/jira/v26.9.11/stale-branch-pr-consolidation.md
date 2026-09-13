# Consolidate stale branches/PRs into main (#93, #70, #67, dependabot, dmedi-solver, ocel-synthetic, mna-replanning, harness, fortune5, gymnasium-replay)

## Summary

A sequence of 16 merge commits on `main` in `~/gymact` consolidated long-outstanding
branches and pull requests (open PRs #93/#70/#67, two Dependabot update branches, and
ten feature/explore/develop/release/docs branches dated 2026-08-23 through
2026-09-02) into `main`. Each merge was performed individually, in dependency order,
with explicit conflict resolution favoring main's newer superseding code where both
sides had touched the same files.

## Status

Done — already merged and committed to `main`.

## Commits

- `ecbb9f6` Merge PR #93: bind cached plans to receipted actuation
- `d635b67` Merge PR #70: keep main's newer superseding envharness reset-cleanup logic
- `fb09bef` Merge PR #67: keep main's newer superseding platform-console provider rewrite
- `487b91d` Merge branch 'origin/explore/dmedi-solver-correspondence-20260823-2322'
- `4bcd733` Merge branch 'origin/feat/gymact-ex-beam-surface'
- `abd961a` Merge branch 'origin/feature/ocel-synthetic-gym-results-20260902'
- `5d64d09` Merge branch 'origin/feat/mna-observed-state-replanning'
- `ec1056a` Merge branch 'origin/dependabot/pip/development-dependencies-e250235a32'
- `ac442a8` Merge branch 'origin/dependabot/github_actions/ci-dependencies-f214ed0868'
- `2179b6d` Merge branch 'origin/develop/select-simulation-conformance-20260823-2031'
- `6441d36` Merge branch 'origin/explore/26.8.23-simulation-courts'
- `561f861` Merge branch 'origin/release/v26.8.23-closure-20260823'
- `9d2bf39` Merge branch 'origin/docs/refresh-agents-20260823'
- `1f3a139` Merge branch 'origin/feat/harness-if-2608-11727'
- `fc9f8c3` Merge branch 'origin/feat/fortune5-public-ontology-paas'
- `02188d2` Merge branch 'origin/explore/gymnasium-replay-restore'

## Changes

Real, substantive changes landed by these merges, per `git show --stat` on each commit:

- **PR #93** (`ecbb9f6`): added `scripts/benchmark_plan_provenance.py`,
  `src/gymact/planning.py` (+108 lines), plan-provenance tests
  (`tests/test_plan_provenance.py`, `tests/test_plan_provenance_enterprise.py`),
  a new CI workflow `.github/workflows/fortune5-planning-crown.yml`, and a
  `terraform_docker/main.tf` fix removing a hardcoded workstation-specific Docker
  socket default in favor of a nullable, provider-resolved host. Conflicting
  copies of `mcp_client_session.py`, `test_platform_console_ontology_provider_chicago.py`,
  and `test_algebra_protocols.py` were resolved by keeping main's newer versions
  (cosmetic/renamed-helper differences only).
- **PR #70** (`d635b67`): kept main's newer superseding envharness reset-cleanup
  logic; no diff stat emitted (pure merge with the "ours"-equivalent side chosen).
- **PR #67** (`fb09bef`): added `.github/workflows/platform-console-current-contract.yml`,
  new module `src/gymact/gyms/semantic_pack_locator.py`, and
  `tests/test_semantic_pack_locator.py`; resolved the platform-console ontology
  provider test conflict by keeping main's newer superseding rewrite of
  `test_platform_console_ontology_provider_chicago.py` (433 lines rewritten).
- **dmedi-solver-correspondence** (`487b91d`): merged in `.act-events/pull-request.json`,
  `.ggen/keys/{signing,verifying}.key`, a new workflow
  `.github/workflows/explore-solver-correspondence-exact-head.yml`, and a batch of
  binary `.eval` task-result fixtures under a dated eval-results directory.
- **gymact-ex-beam-surface** (`4bcd733`): added a new Elixir/BEAM surface
  (`beam/gymact_ex/`) — `mix.exs`, `lib/gymact_ex.ex`, `lib/gymact_ex/client.ex`
  (220 lines), `lib/gymact_ex/error.ex`, a Chicago-style ExUnit test
  (`test/gymact_ex_chicago_test.exs`), plus `scripts/chicago_gymact_ex.sh` and
  `scripts/chicago_gymact_ex_server.py`, and CI workflow `gymact-ex.yml`.
- **ocel-synthetic-gym-results** (`abd961a`): added `src/gymact/synthetic_ocel.py`
  (214 lines), extended `src/gymact/manufacture.py` (+74 lines), added
  `docs/synthetic-ocel-results.md` and `tests/test_synthetic_ocel_results.py`
  (146 lines), and extended `.claude/rules/ggen-boundary.md`.
- **mna-observed-state-replanning** (`5d64d09`): added
  `scripts/run_fortune5_mna_replan_episode.py` (123 lines),
  `scripts/verify_v2691_world_execution.py`, and `tests/test_mna_gym.py` (40 lines).
- **dependabot/pip** (`ec1056a`): updated development dependency version pins in
  `pyproject.toml` (12 lines changed).
- **dependabot/github_actions** (`ac442a8`): bumped pinned GitHub Actions versions
  across ~20+ workflow files (`.github/workflows/*.yml`), including `ci.yml`,
  `envharness.yml`, and multiple `explore-*.yml` workflows.
- **develop/select-simulation-conformance** (`2179b6d`): added a
  `develop_simulation_conformance` module (`calibration.py`, `currentness.py`,
  `idempotency.py`, `identity.py`, `partial_order.py`, `provider_oracle.py`,
  `qualification.py`) plus its selection record JSON and
  `test_selected_simulation_conformance.py`.
- **explore/26.8.23-simulation-courts** (`6441d36`): added five exploratory test
  modules under `tests/explore/` (idempotency collision, partial-order trace
  normalization, provider differential oracle, semantic currentness vector,
  stochastic transition calibration).
- **release/v26.8.23-closure** (`561f861`): release-closure changes — updated
  `CHANGELOG.md`, bumped `pyproject.toml` version, bumped
  `src/gymact/__init__.py`, and touched multiple files under
  `explore_decision_transport/` and `explore_replicated_projection_quorum/`
  (balance, divergence, methodology, pareto, proof, qualification, receipt,
  risk, subject, support, weights, worst_stratum, admission, audit, causality,
  clock, engine, failure, quorum, etc.).
- **docs/refresh-agents** (`9d2bf39`): added 20 lines to `AGENTS.md`.
- **feat/harness-if-2608-11727** (`1f3a139`): added `src/gymact/harness_if.py`
  (982 lines), `src/gymact/harness_if_semantic.py` (202 lines),
  `tests/test_harness_if.py` (300 lines), and `tests/test_harness_if_semantic.py`
  (97 lines).
- **feat/fortune5-public-ontology-paas** (`fc9f8c3`): added a new Elixir PaaS
  surface under `paas/` — `control_plane.ex`, `profile.ex`, `repo.ex`, a Mix
  generate task, two TTL ontology files (`fortune5-cloud-profile.ttl`,
  `provider-catalog.ttl`), ExUnit tests, and workflow `fortune5-paas.yml`.
- **explore/gymnasium-replay-restore** (`02188d2`): reworked
  `src/gymact/gyms/gymnasium_env.py` (177 lines changed), added
  `tests/test_gymnasium_replay_restore_explore.py` (171 lines), and added
  workflow `.github/workflows/gymnasium-replay.yml`.

## Verification

None stated in any of the 16 commit messages or diffs — no test/lint/CI run output
is quoted in the merge commit messages themselves. Several merges add or modify CI
workflow files (e.g. `fortune5-planning-crown.yml`, `platform-console-current-contract.yml`,
`gymact-ex.yml`, `fortune5-paas.yml`, `gymnasium-replay.yml`) and test files (e.g.
`test_plan_provenance.py`, `test_semantic_pack_locator.py`, `test_mna_gym.py`,
`test_harness_if.py`, `test_synthetic_ocel_results.py`,
`test_gymnasium_replay_restore_explore.py`), but no evidence of an actual run
(exit code, pass/fail count) is present in the commit history reviewed for this
ticket.

## Related

- PR #93 — "bind cached plans to receipted actuation"
- PR #70 — envharness reset-cleanup logic
- PR #67 — "platform-console provider rewrite"
- Branch `origin/explore/dmedi-solver-correspondence-20260823-2322`
- Branch `origin/feat/gymact-ex-beam-surface`
- Branch `origin/feature/ocel-synthetic-gym-results-20260902`
- Branch `origin/feat/mna-observed-state-replanning`
- Branch `origin/dependabot/pip/development-dependencies-e250235a32`
- Branch `origin/dependabot/github_actions/ci-dependencies-f214ed0868`
- Branch `origin/develop/select-simulation-conformance-20260823-2031`
- Branch `origin/explore/26.8.23-simulation-courts`
- Branch `origin/release/v26.8.23-closure-20260823`
- Branch `origin/docs/refresh-agents-20260823`
- Branch `origin/feat/harness-if-2608-11727`
- Branch `origin/feat/fortune5-public-ontology-paas`
- Branch `origin/explore/gymnasium-replay-restore`
