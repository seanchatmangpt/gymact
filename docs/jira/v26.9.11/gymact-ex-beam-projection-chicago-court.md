# In-repo GymActEx BEAM projection + real Chicago court

## Summary

Added an Elixir (BEAM) client projection of the canonical GymAct HTTP contract,
under `beam/gymact_ex/`, plus a real, no-mock cross-runtime "Chicago court"
(state-based integration test) that runs a real Python GymAct server and
exercises the Elixir client against it over real HTTP. Includes a CI workflow
to qualify the BEAM-to-Python boundary and several follow-up fixes to the test
harness script.

## Status

Done — already merged/committed. All commits below are present in the current
branch history of `~/gymact`.

## Commits

- `1b86eb1` feat(gymact_ex): add in-repo BEAM projection
- `c6c8da8` feat(gymact_ex): model HTTP boundary errors
- `5c815f1` feat(gymact_ex): project canonical GymAct HTTP contract
- `8396c82` feat(gymact_ex): expose bounded execution API
- `30e5491` docs(gymact_ex): define semantic boundary
- `45798c3` test(gymact_ex): configure explicit Chicago court
- `5792539` test(gymact_ex): add real cross-runtime Chicago court
- `f63789d` test(gymact_ex): add real GymAct Chicago server
- `6b504f6` test(gymact_ex): wire no-mock cross-runtime court
- `5369afb` ci(gymact_ex): qualify real BEAM to Python boundary
- `c0b0600` fix(gymact_ex): keep default-arg wrappers explicit
- `71ab18b` fix(gymact_ex): let Chicago court test semantics not formatter drift
- `335e0b0` fix(gymact_ex): resolve Python env without nonexistent lock

## Changes

- `beam/gymact_ex/mix.exs` (31 lines added): new Mix project scaffold for the
  `gymact_ex` Elixir application — the in-repo BEAM projection.
- `beam/gymact_ex/lib/gymact_ex/error.ex` (25 lines added): models HTTP
  boundary error cases for the client.
- `beam/gymact_ex/lib/gymact_ex/client.ex` (220 lines added): the client
  module projecting the canonical GymAct HTTP contract into Elixir.
- `beam/gymact_ex/lib/gymact_ex.ex` (29 lines added, later touched by
  `c0b0600`): the top-level public/bounded execution API surface for the
  library.
  - `c0b0600` (7 insertions / 3 deletions) subsequently kept default-argument
    wrapper functions explicit rather than relying on implicit multi-arity
    generation.
- `beam/gymact_ex/README.md` (90 lines added): documents the semantic boundary
  of the projection (what this library is and is not responsible for).
- `beam/gymact_ex/test/test_helper.exs` (5 lines added): explicit ExUnit test
  configuration for the Chicago-style court.
- `beam/gymact_ex/test/gymact_ex_chicago_test.exs` (87 lines added): the real
  cross-runtime Chicago court test — exercises the Elixir client against a
  live server rather than a mock.
- `scripts/chicago_gymact_ex_server.py` (30 lines added): a real Python
  GymAct server used as the live counterparty for the Chicago court, run as
  an actual process rather than stubbed.
- `scripts/chicago_gymact_ex.sh` (51 lines added, then patched twice):
  orchestration script that wires the no-mock cross-runtime court end to end
  (starts the Python server, runs the Elixir test suite against it).
  - `71ab18b` (1 deletion): removed `mix format --check-formatted` from the
    script so the court tests semantics, not formatter drift.
  - `335e0b0` (3 insertions / 1 deletion): changed `uv sync --frozen` to
    `uv sync`, with an inline comment noting the repo does not commit
    `uv.lock`, so a frozen-lock replay would have been a false claim.
- `.github/workflows/gymact-ex.yml` (49 lines added): CI workflow that
  qualifies the real BEAM-to-Python boundary (runs the Chicago court in CI).

## Verification

- CI: `.github/workflows/gymact-ex.yml` was added specifically to run/qualify
  this boundary in CI (per commit `5369afb`); no CI run output is included in
  the commit messages themselves.
- Local court: `scripts/chicago_gymact_ex.sh` runs `mix deps.get` and the
  ExUnit suite (`gymact_ex_chicago_test.exs`) against a real, locally started
  Python server (`chicago_gymact_ex_server.py`) — described in commit
  subjects as a "real cross-runtime Chicago court" / "no-mock cross-runtime
  court."
- No test/lint output, pass/fail counts, or run logs are stated in any commit
  message — none stated beyond what the script and CI workflow files
  themselves define.

## Related

- No PR numbers or branch names are referenced in any of the commit subjects
  or messages above.
