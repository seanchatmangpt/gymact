# gymact Jira-style backlog — 2026-08-13

Source: findings confirmed in a prior session (this session's task is to
record them as a backlog, not to re-derive them). Each ticket cites the
finding as given.

### GYMACT-1: dev_portfolio.py not registered in registry.py/combinatorial_ocel.py
- **Status**: In Progress
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
- **Status**: In Progress
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
- **Status**: Open
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
- **Status**: Open
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
