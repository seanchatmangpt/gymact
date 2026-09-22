# gymact Jira-style backlog — 2026-08-13

Source: findings confirmed in a prior session (this session's task is to
record them as a backlog, not to re-derive them). Each ticket cites the
finding as given.

### GYMACT-1: dev_portfolio.py not registered in registry.py/combinatorial_ocel.py
- **Status**: Done (2026-09-21) -- fix landed in 569d777; real enumeration call re-run this
  session finds `dev-portfolio` in both `registry.builtin_provider_names()` and
  `combinatorial_ocel.GYM_FACTOR.alternatives` (see SJ-008 re-verification note).
- **Priority**: P1
- **Evidence**: `src/gymact/gyms/dev_portfolio.py` found unregistered in
  `registry.py` and `combinatorial_ocel.py` (prior session finding).
- **Description**: The dev_portfolio gym provider exists in the gyms
  directory but was not wired into the registry or the combinatorial OCEL
  index, so it is invisible to whatever enumerates registered gyms. Being
  fixed concurrently in this same run.
- **Definition of done**: `dev_portfolio.py`'s provider class appears in
  `registry.py`'s registration set and in `combinatorial_ocel.py`'s gym
  index, verified by a real lookup/enumeration call finding it, not by
  reading the source and assuming.

### GYMACT-2: dev_portfolio.py docstring makes a false, grep-checkable claim
- **Status**: Done (2026-09-21) -- correction landed in 569d777; DoD grep re-run for real and
  the docstring matches it (see SJ-008 re-verification note).
- **Priority**: P2
- **Evidence**: `src/gymact/gyms/dev_portfolio.py` docstring claims no other
  gym calls the gh/GitHub API; this claim is grep-checkable and false
  (prior session finding).
- **Description**: The docstring asserts uniqueness that a real grep across
  `src/gymact/gyms/` does not support — other gym(s) call the GitHub API
  too. Being fixed concurrently in this same run.
- **Definition of done**: The docstring is corrected to match a real,
  currently-run `grep -rn "gh \|github\|GitHub" src/gymact/gyms/` result, or
  removed if it cannot be stated precisely.

### GYMACT-3: CLAUDE.md routing table cites docs/STATUS.md and docs/ecosystem-standing.md, neither exists
- **Status**: Done / Not-reproducible (2026-09-21) -- neither file is cited by the current
  `CLAUDE.md` or `.claude/rules/*.md`, and every path they do cite resolves to a real file
  (see SJ-008 re-verification note).
- **Priority**: P1
- **Evidence**: `~/gymact/CLAUDE.md`'s "Look this up when you are doing
  that" table and `.claude/rules/standing-law.md` both cite
  `docs/STATUS.md` and `docs/ecosystem-standing.md`; confirmed via
  `find`/`ls` that neither file exists anywhere in the repo.
- **Description**: The routing table that is supposed to tell a reader
  where standing/status claims live points at two files that do not exist
  in this checkout. Real candidate files with similar content do exist
  (`docs/sota-standing.md`, `docs/audits/2026-08-08-stubs-wip.md`, etc.),
  suggesting the table was copied from a sibling repo (autofde-lab) rather
  than authored for this one.
- **Definition of done**: Either (a) `docs/STATUS.md` and
  `docs/ecosystem-standing.md` are created with real content, or (b)
  `CLAUDE.md` and `.claude/rules/standing-law.md` are corrected to point at
  the files that actually exist in this repo (e.g.
  `docs/sota-standing.md`, `docs/audits/2026-08-08-stubs-wip.md`) —
  verified by `find ~/gymact -name "<cited-filename>"` returning a real
  match for every path the routing table cites.

### GYMACT-4: 8 real pytest failures reported, then two immediate re-runs both passed clean — UNVERIFIED, not resolved
- **Status**: Done (2026-09-21) -- isolated full-suite re-run executed twice with real output
  recorded (SJ-008 note). 2 of the 8 named failures reproduce deterministically -> root-caused
  follow-ups GYMACT-5 and GYMACT-6; the other 6 did not reproduce -> recorded-negative on this
  head. Suite is still red for environmental reasons (GYMACT-7).
- **Priority**: P0
- **Evidence**: A prior full pytest run reported 8 real failures:
  `test_default_verifier_catches_a_dishonest_providers_false_success_claim`,
  `test_gym_is_actuated_per_its_real_ocel_log` parametrized for
  dev-portfolio/qqr/r2e-gym/terraform-plan-terragoat-alicloud,
  `test_every_real_gym_provider_class_is_registered_or_allowlisted`,
  `test_fastapi_contract_and_evidence_share_runtime_identity`,
  `test_real_episode_replays_from_captured_state_with_no_subprocess`. Two
  independent immediate re-runs of the identical command both showed exit
  0 with zero failures.
- **Description**: This is a direct contradiction, not a resolved flake:
  one run produced 8 named failures, the next two runs of the same command
  produced zero. This session does not know whether the failures were
  genuine intermittent defects (e.g. real ordering/isolation bugs,
  resource contention) or an artifact of a concurrent session touching the
  same checkout at the time of the first run. Neither "the suite is
  broken" nor "the suite is fine" is supported by the evidence as it
  stands — both are asserted here as open, not settled.
  Per `absence-is-not-evidence.md`-style discipline (imported into this
  portfolio's sibling repo, same standard applies here): absence of a
  repeat failure is not proof the original failure was spurious.
- **Definition of done**: A clean, isolated re-run (fresh checkout or
  confirmed no concurrent process touching this working tree, no other
  session running pytest against the same paths) of the exact same pytest
  invocation, run to completion, with its real output pasted. If the 8
  failures reproduce under isolation, file follow-up tickets per failing
  test with root cause. If they do not reproduce under isolation across
  multiple runs, downgrade this ticket to a recorded-negative note citing
  the exact isolated command and output, rather than closing it silently.

---

## Follow-up tickets filed by GYMACT-4 (2026-09-21, root-caused from isolated runs)

### GYMACT-5: test_verify_replay imports a half-initialised, module-level-skipped test module
- **Status**: Open
- **Priority**: P2
- **Evidence**: `tests/test_verify_replay.py::test_real_episode_replays_from_captured_state_with_no_subprocess`
  FAILED in both isolated full runs with
  `ImportError: cannot import name 'AUTHORITY' from 'tests.test_terraform_plan'`
  (test_verify_replay.py:70). Run alone it does not fail (it skips).
- **Root cause**: `tests/test_terraform_plan.py:127` calls `pytest.skip(...)` at module level
  (terragoat submodule / terraform binary absent under `~/autofde-lab/vendor/gyms/terragoat`)
  before `AUTHORITY` is defined at line 143. During a full run the module is already in
  `sys.modules` in that half-initialised state, so the later `from .test_terraform_plan import
  AUTHORITY` raises ImportError (a failure) instead of the `Skipped` it raises when the module is
  imported fresh. Environment gap turned into a test-order-dependent failure.
- **Definition of done**: the replay test skips (named reason) or passes identically whether run
  alone or in the full suite; `AUTHORITY` etc. move to a module that has no module-level skip.
  Out of this order's `path_scope` (tests/), so filed, not fixed.

### GYMACT-6: unclosed dspy/diskcache sqlite connection + event loop blamed on unrelated tests
- **Status**: Open
- **Priority**: P1
- **Evidence**: isolated full runs 7 and 8 both FAIL, with `PytestUnraisableExceptionWarning`
  (`ExceptionGroup: multiple unraisable exception warnings (3 sub-exceptions)`):
  `test_kernel_verification.py::test_default_verifier_catches_a_dishonest_providers_false_success_claim`,
  `test_envharness.py::test_stage_cannot_bypass_fail_closed_authority`,
  `test_world_cyber.py::test_kernel_refuses_ambient_do_and_receipts_authorized_actuation`,
  `test_dspy_verifier_chicago.py::TestGepaOptimizesTheRealJudge::test_gepa_optimized_program_scores_at_least_as_well_as_the_base_program`.
  The kernel, envharness and world_cyber tests pass when run alone (real run of those tests plus
  test_verify_replay: 3 passed, 1 skipped, 0 failed).
- **Root cause**: `pyproject.toml` `filterwarnings = ["error", ...]` converts a GC-time
  `ResourceWarning` into a hard failure of whichever test is running when the collector fires.
  The leaked objects are an `sqlite3.Connection` allocated at `dspy/clients/cache.py:133`
  (`disk_cache.get` -> `diskcache`) and an unclosed `_UnixSelectorEventLoop`. The blamed test is
  therefore unrelated to the leak and the blame moves with collection order and GC timing, which
  is the observed "8 failures, then clean re-runs" signature of GYMACT-4 (same class as the
  rdflib GC-timing artifact receipted in 0d2d781). The kernel dishonest-provider test named in
  GYMACT-4 is one of these.
- **Definition of done**: the dspy cache/event loop is closed deterministically (fixture that
  closes `dspy.cache.disk_cache` and the loop) so no unraisable warning is emitted; the four
  tests above pass in a full isolated run.

### GYMACT-7: environment-gated failures reproduced under isolation (not code defects here)
- **Status**: Open (environmental)
- **Priority**: P3
- **Evidence and root cause** (from the same two isolated runs):
  - `tests/test_declare_conformance.py` x2: `wpm mining mine-declare failed (exit=2)` --
    `error: unrecognized subcommand 'mine-declare'` from the `~/wasm4pm` `wpm` build (stale
    binary vs. the subcommand the test calls; cargo also errors on
    `{{project-name}}` in an affidavit template Cargo.toml).
  - `tests/test_swegym_live.py` x2: `ActuationResult(accepted=False, standing=BLOCKED,
    reason='ACTUATION_TIMEOUT')` from real docker grading (no/unreachable docker or too slow).
  - `tests/test_cube_container_counter.py`: collection ImportError, vendored
    `~/autofde-lab/vendor/gyms/cube-standard/examples/toy_benchmark/counter.py` missing and docker
    extra unavailable.
- **Definition of done**: run in an environment with the wasm4pm `wpm` that has `mine-declare`, a
  reachable docker daemon, and the cube-standard submodule checked out; or convert to named
  `require_standing` skips.

---

## SJ-008 re-verification -- 2026-09-21

Order SJ-008, worktree `/Users/sac/xaas-worktrees/sjira/sj-008` of seanchatmangpt/gymact, base
`4ab72e6`, branch `sjira/sj-008`. SA2A admission receipt for the order: `rec-a03b5d87`
(autofde beam-bridge, KNOWN, CONFORMS_TO_SPEC). Worker: mixed. The zcode default agent drafted
the first version of the Status edits and a source-level note but its session had no permission
client for execution, so it ran no Python and no pytest; every command result below was run by
the supervising session and its exit code is the observed one.

### GYMACT-1 -- real enumeration call
`PYTHONPATH=src /Users/sac/gymact/.venv/bin/python -c "import gymact.registry as r,
gymact.combinatorial_ocel as c; ..."` (gymact imported from the worktree `src`), exit 0:

```text
dev-portfolio in registry.builtin_provider_names(): True
dev-portfolio in combinatorial_ocel.GYM_FACTOR.alternatives: True
```

Source anchors: `registry.py:20,57`, `combinatorial_ocel.py:65,293`. Fix landed in `569d777`.

### GYMACT-2 -- DoD grep re-run
`grep -rn '"gh"' src/gymact/gyms/ --include="*.py"` -> exactly two gyms issue real `gh` calls:
`chatman_state.py:166,199` and `dev_portfolio.py:138,145,151`. The `dev_portfolio.py` docstring now
names `chatman_state.py` (`discover_github_repos`/`count_github_repos`) as an existing `gh` caller
instead of claiming uniqueness, so it matches the grep result.

### GYMACT-3 -- premise does not reproduce
- `find <worktree> -name STATUS.md` and `-name ecosystem-standing.md` (excluding `.git`, `.venv`)
  return nothing, and `grep -rn "STATUS.md\|ecosystem-standing" CLAUDE.md .claude/rules/` returns
  nothing (exit 1): neither current file cites either name. `git log -S "ecosystem-standing.md"
  --all` shows the string only in this backlog (`771d538`).
- Every repo path cited by `CLAUDE.md` and `.claude/rules/*.md` exists:
  `.claude/rules/{actuation-authority,explore-exploit,ggen-boundary,ocel-standing,ontology,
  python-native}.md` and `docs/synthetic-ocel-results.md`; the one non-repo citation,
  `~/.claude/rules/testing-chicago-style.md`, exists at user level. `.claude/rules/standing-law.md`
  is not present in this repo.
- Real candidates the ticket named exist: `docs/sota-standing.md`.

### GYMACT-4 -- isolated full-suite runs (all commands run from the worktree, exact head 4ab72e6)

| run | command (env) | result |
|-----|---------------|--------|
| 1 | `PYTHONPATH=src /Users/sac/gymact/.venv/bin/python -m pytest -q` | exit 2, 18 collection errors (venv lacks optional extras: gymnasium, dspy, SpiffWorkflow, ...) |
| 2 | same with `/Users/sac/autofde-lab/.venv/bin/python` | exit 4, `'asyncio' not found in markers` (no pytest-asyncio) |
| 3, 4 | `uv sync --all-extras --group dev` into a private env, then `PYTHONPATH=src <env>/python -m pytest -q` | exit 2 both, 5 collection errors (browsergym x2, cube, kubernetes, terraform: standings unavailable) |
| 5 | as 3 plus `GYMACT_ALLOW_DEGRADED_STANDINGS='*'` | exit 2, 1 collection error (cube_container_counter) |
| 6 | as 5 plus `--continue-on-collection-errors` | pytest aborted in its own teardown (`PermissionError` removing a garbage dir under the shared `~/.cache/tmp/pytest-of-sac`); no summary; not counted |
| 7, 8 | as 6 plus `-p no:cacheprovider --basetemp <private dir> --junitxml=<file>` | exit 1 both, identical: 1663 tests, 9 failures, 1 error, 20 skipped (junit) |

Isolation facts: the worktree is private to this session and only this session ran pytest in it.
One unrelated foreign pytest (pid 72755, cwd `/private/tmp/t1-probe-gym`, a different tree) was
observed at 0.0% CPU immediately before run 1 and was not re-checked afterwards. The shared default pytest temp root is itself a cross-session hazard (run 6), so runs
7 and 8 used private `--basetemp` directories. The suite also mutates tracked files
(`reports/ocel/crown-p1-{allowed,denied}/episode.ocel.json`,
`tests/fixtures/real_episode.ocel.json`) and writes `.inspect_logs/`; those were restored with
`git restore` before commit, and two concurrent sessions in one checkout would race on them.

The 9 failures of runs 7 and 8 (same set both times):
`test_declare_conformance` x2, `test_swegym_live` x2 (GYMACT-7);
`test_kernel_verification` dishonest-provider, `test_envharness` fail-closed-authority,
`test_world_cyber` ambient-DO, `test_dspy_verifier_chicago` GEPA (GYMACT-6);
`test_verify_replay` no-subprocess replay (GYMACT-5). The 1 error is the cube collection failure.

Against the 8 names in the ticket:
- Reproduced, deterministic across two isolated runs: `test_default_verifier_catches_a_dishonest_providers_false_success_claim`
  (GYMACT-6) and `test_real_episode_replays_from_captured_state_with_no_subprocess` (GYMACT-5).
- Not reproduced in either isolated run (recorded-negative, exact command above, runs 7 and 8):
  `test_gym_is_actuated_per_its_real_ocel_log` for dev-portfolio, qqr, r2e-gym and
  terraform-plan-terragoat-alicloud; `test_every_real_gym_provider_class_is_registered_or_ontology_excluded`
  (renamed from `..._or_allowlisted`); `test_fastapi_contract_and_evidence_share_runtime_identity`.
  Absence of a repeat failure is not proof the first failure was spurious; the recorded-negative
  covers only these two runs on this head.
- The GC-attribution mechanism of GYMACT-6 explains why the blamed test set changes between
  sessions while a clean re-run shows none.

Order-level runnable check (`python -m pytest -q`): NOT passing. Best real result exit 1 (9 failed,
1 collection error) with the fully-provisioned env and degraded standings allowed; exit 2 without
that opt-in. None of the failures touch `src/gymact/gyms/dev_portfolio.py` or the backlog file
(this diff is docs only), and the base-commit receipt (`4ab72e6`) already reports remaining
environmental failures.
