# Merge #133 GymActEx BEAM projection/court + close real gaps from mass branch merge

## Summary

Merged PR #133 (`feat/gymact-ex-beam` -> main), which adds an in-repo GymActEx
BEAM (Elixir) projection of the GymAct client plus a Chicago-style
cross-runtime qualification court, into main. Separately, merged all 30 open
PRs/remote branches into main and closed the real test/config gaps that
surfaced from that merge (dependency floors, stale tests, a docker-context
resolution bug, a resurrected stale test, and several assertion/detection
fixes). This ticket documents the completed, already-merged/committed state
of that work — it is not a backlog item.

## Status

Done — already merged/committed on main.

## Commits

- `a2e97fd` feat: add in-repo GymActEx BEAM projection and Chicago court (#133)
- `7b70419` feat: add in-repo GymActEx BEAM projection and Chicago court (#133)
- `0d2d781` fix: close real gaps surfaced by merging all open branches/PRs into main
- `2273b33` fix: re-remove superseded pre-rescope platform-console Chicago test

## Changes

### #133 — GymActEx BEAM projection and Chicago court (`a2e97fd`, `7b70419`)

Merge commit (parents `2ce639c` + `5b38c02`); identical stat/message appears
twice in the requested hash list (`a2e97fd` and `7b70419` are the same merge
commit content):

- `beam/gymact_ex/lib/gymact_ex.ex`, `beam/gymact_ex/lib/gymact_ex/client.ex`
  (220 lines), `beam/gymact_ex/lib/gymact_ex/error.ex` — new Elixir client
  projection of the GymAct HTTP API.
- `beam/gymact_ex/mix.exs`, `beam/gymact_ex/README.md` — new Mix project
  scaffolding and docs for the BEAM projection.
- `beam/gymact_ex/test/gymact_ex_chicago_test.exs`,
  `beam/gymact_ex/test/test_helper.exs` — new Chicago-style (real
  collaborator, state-based) test suite for the Elixir client.
- `.github/workflows/gymact-ex.yml` — new CI workflow for the BEAM projection.
- `scripts/chicago_gymact_ex.sh`, `scripts/chicago_gymact_ex_server.py` — new
  scripts to run a real local server and drive the Chicago court against it.
- Multiple files under `explore_replicated_projection_quorum/` (admission.py,
  audit.py, causality.py, clock.py, engine.py, failure.py, pareto.py,
  quorum.py, receipt.py, refusal.py, replica.py) — real edits (2-69 line
  changes each) as part of "RPQ exact-head repair courts" referenced in the
  merge message.

### Mass branch/PR merge + gap closure (`0d2d781`)

Merged all 30 open PRs/remote branches (agent/dependabot/explore/feat/fix)
into main via `git merge --no-ff` (no rebase, no force-push). 27 merged with
zero conflicts; 3 had genuine content conflicts, resolved by inspecting both
sides' timestamps/semantics:

- Kept main's newer superseding rewrites for
  `platform_console_ontology_provider.py` and `envharness.py`
  reset-cleanup logic.
- Took the incoming PR's real portability fix for
  `terraform_docker/main.tf`'s `docker_host` default.

Gaps closed post-merge (each a real fix, not a loosened assertion):

- `pyproject.toml`: relaxed the `gyms` extra's botocore floor (a dependabot
  bump had pinned `botocore>=1.43.83`, incompatible with inspect-ai's
  aioboto3 dependency chain); declared `networkx` in the dev group (required
  directly by the sibling `~/POWL` checkout's
  `tests/powl/test_reference_model_conformance.py`).
- `ggen/gymact-registry-pack/exclusions.ttl`: removed a duplicate
  `DependencyWorldProvider`/`SharedDependencyWorldProvider` exclusion pair
  introduced by one of the merged branches.
- `tests/test_composition_inventory_completeness_chicago.py`: catalogued
  `PlatformConsoleOntologyDrivenProvider` and
  `FailClosedPlatformConsoleAuthorityResolver` in
  `_INTENTIONALLY_UNCATALOGED`, matching the existing
  `rg:x-platform-console-ontology-driven` exclusion.
- Deleted `tests/test_platform_console_ontology_provider_chicago.py` again
  (a merged branch predating commit `574e57b` had resurrected an already
  stale/removed test calling a factory signature that no longer exists) —
  the standalone re-fix of this is also captured separately in `2273b33`.
- `src/gymact/connection.py`, `tests/test_connection.py`,
  `tests/test_evidence_sota.py`: admitted the new
  `synthetic-ocel-result-contract.jcs.json` file into the manufacturing
  bundle's expected surface (added by the OCEL-synthetic-results PR).
- `tests/test_core.py`: dropped a stale hardcoded CLI version literal
  (`"26.8.7"`) in favor of `importlib.metadata.version("gymact")`; removed
  the optional `ggen_agent_*` tool names from the no-`ggen_agents` FastMCP
  surface test.
- `tests/test_fastmcp_ontology_closure.py`: extended the AST-based
  `_source_tools()` helper to also detect the `mcp.tool()(fn)` call-style
  registration (previously only `@mcp.tool()` decorator syntax was
  detected), closing a real detection blind spot vs. the always-13-tool
  ontology surface.
- `tests/explore_evidence_composition/test_interval_semiring.py`: switched
  an exact float equality assertion to `math.isclose` (a floating-point
  precision mismatch, `0.5599999999999999` vs `0.56`, not a logic bug).
- `tests/explore_process_transition_correspondence/test_evidence_frontier.py`:
  fixed a test fixture bug — it asserted a `STALE_OR_FUTURE` refusal using
  two `SubjectEpoch`s on different subjects, which real `admit_evidence()`
  correctly refuses earlier as `REFUSED_FOREIGN_SUBJECT_EVIDENCE`; the
  fixture now holds the subject constant and varies only the generation.
- `src/gymact/gyms/terraform_docker_apply.py`: added
  `_discover_active_docker_context_host()`, a real `docker context inspect`
  query used only when the caller passes no explicit `docker_host` and
  `DOCKER_HOST` is unset — closes a real local-environment gap (this
  machine's active Docker daemon is Colima's
  `~/.colima/default/docker.sock`, not the classic
  `/var/run/docker.sock` both the old hardcoded default and the incoming
  PR's nullable-provider-default resolved to; all 3 real Docker actuation
  tests failed with `container_running: False` until this fix).

### Re-remove superseded pre-rescope platform-console test (`2273b33`)

- Deleted `tests/test_platform_console_ontology_provider_chicago.py` (221
  lines removed). This test called
  `build_platform_console_ontology_provider(pack_dir=...)`, a signature the
  current factory in
  `src/gymact/gyms/platform_console_ontology_provider.py` no longer has (it
  takes no arguments and reads canonical RDF directly). Commit `574e57b`
  had already deleted this stale test; a later-merged branch (predating
  `574e57b`) resurrected it during the PR merge sweep. PR #93
  (`feat/continuous-plan-provenance`) independently deleted the same file,
  agreeing with `574e57b`'s intent. Restoring the deletion closed 4 real
  test failures.

## Verification

Stated directly in the `0d2d781` commit message:

- Full `pytest` suite run with `GYMACT_ALLOW_DEGRADED_STANDINGS=*`: 1627
  tests, 0 collection errors, 26 legitimate environment-gated skips (no
  reachable k8s cluster, no browsergym/cube extras, etc. — real skip
  reasons, not mocked).
- Two re-runs converged to the same 6 remaining failures, independently
  confirmed to pass in isolation; traced to a shared GC-timing artifact
  (rdflib's SQLite-backed store surfacing a `ResourceWarning` as an
  unraisable-exception failure depending on run order) plus one
  pre-existing external-tool environment quirk (the locally installed
  `ggen` v26.8.28 binary's own config-path discovery, already documented
  as CI-toolchain-pinned) — both confirmed pre-existing, not caused by
  this session's merges.
- `2273b33`: "Restoring the deletion closes the resulting 4 real test
  failures" (stated in commit message; no separate CI run output quoted).

No test/lint/CI evidence is stated in the `a2e97fd`/`7b70419` (#133) commit
messages beyond the merge message itself referencing "real cross-runtime
Chicago qualification and RPQ exact-head repair courts" — none stated
beyond that reference.

## Related

- PR #133 — GymActEx BEAM projection and Chicago court.
- PR #93 (`feat/continuous-plan-provenance`) — independently deleted the
  same stale platform-console test file referenced in `2273b33`.
- Prior commit `574e57b` — original deletion of the stale
  `test_platform_console_ontology_provider_chicago.py`, restored by
  `0d2d781`/`2273b33` after a merged branch resurrected it.
- Branch `feat/gymact-ex-beam` (source of #133, per merge parent `5b38c02`).
