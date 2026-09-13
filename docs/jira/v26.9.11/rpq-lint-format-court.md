# RPQ exact-head lint/format court + pytest+unittest discovery

## Summary

Closed out the exact-head lint/formatting court for the
`explore_replicated_projection_quorum` (RPQ) module in `~/gymact`, and fixed
test discovery so RPQ tests are collectible under both `pytest` and stdlib
`unittest`. Work spans package-safe imports for RPQ test helpers, Ruff-driven
lint/format fixes across the RPQ source and test files, and a follow-up
formatting correction to match exact Ruff formatter output.

## Status

Done — already merged/committed on the current branch. No open work items
remain from this ticket; it documents completed history only.

## Commits

- `29e0139` fix(tests): make RPQ helper imports package-safe
- `f4eabd2` fix(tests): support pytest and unittest RPQ discovery
- `f2bdbc6` fix(rpq): close exact-head lint and formatting court
- `5b38c02` style(rpq): match exact Ruff formatter output

## Changes

- Added `tests/explore_replicated_projection_quorum/__init__.py` and switched
  RPQ test files' internal helper imports to package-relative form so the
  test directory is a proper importable package (`29e0139`).
- Adjusted import statements across `test_rpq_admission.py`,
  `test_rpq_causality.py`, `test_rpq_chicago.py`, `test_rpq_failure.py`,
  `test_rpq_quorum.py`, `test_rpq_selectors.py`, `test_rpq_subject_replica.py`,
  and `test_rpq_window_universe.py` so the same test modules are discoverable
  and runnable by both `pytest` and stdlib `unittest` (`f4eabd2`).
- Applied Ruff-style lint/formatting fixes across the RPQ source package
  (`admission.py`, `audit.py`, `causality.py`, `clock.py`, `engine.py`,
  `failure.py`, `pareto.py`, `quorum.py`, `receipt.py`, `refusal.py`,
  `replica.py`, `selectors.py`, `storage.py`, `subject.py`, `universe.py`,
  `window.py`, `world.py`) — e.g. in `quorum.py`, inserted PEP 8 blank-line
  separation between top-level definitions and reformatted multi-line
  `QuorumAssessment` constructor calls (previously single-line, now
  one-argument-per-line) to match Ruff's formatter output (`f2bdbc6`).
- Made corresponding lint/format-driven adjustments to RPQ test files
  (`test_rpq_admission.py`, `test_rpq_chicago.py`, `test_rpq_clock.py`,
  `test_rpq_failure.py`, `test_rpq_pareto.py`, `test_rpq_quorum.py`,
  `test_rpq_receipt_authority.py`, `test_rpq_storage.py`) in the same
  commit (`f2bdbc6`).
- Follow-up fix to `selectors.py` (8 lines changed, net -4) to match the
  exact Ruff formatter output that `f2bdbc6` had not fully converged on
  (`5b38c02`).

## Verification

None stated. The four commit messages contain only a subject line each — no
body text referencing test runs, lint output, or CI results. No PR or CI
reference appears in any of the four commit subjects or bodies.

## Related

No PR numbers or branch names are mentioned in any of the four commit
subjects.
